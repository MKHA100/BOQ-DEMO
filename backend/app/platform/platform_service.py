from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from secrets import token_urlsafe
from uuid import uuid4

from app.auth.passwords import hash_password
from app.core.errors import bad_request, forbidden, not_found
from app.platform.platform_repository import platform_repository
from app.projects.project_service import project_service

SYSTEM_PERMISSIONS = {
    "super_admin": ["*"],
    "organization_admin": [
        "manage_organization",
        "invite_member",
        "manage_roles",
        "create_project",
        "manage_projects",
        "view_billing",
    ],
    "project_manager": ["create_project", "manage_projects"],
    "quantity_surveyor": ["create_project", "view_project"],
    "reviewer": ["view_project"],
    "viewer": ["view_project"],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    text = "".join(char.lower() if char.isalnum() else " " for char in value)
    return "-".join(part for part in text.split() if part)[:80] or "item"


class PlatformService:
    def current_context(self, user: dict) -> dict:
        organization = self.primary_organization(user["id"])
        is_super_admin = user.get("role") == "super_admin"
        effective_role = "super_admin" if is_super_admin else (organization or {}).get("membership_role") or user.get("role") or "viewer"
        return {
            "user": user,
            "organization": organization,
            "membership_role": effective_role,
            "permissions": self.permissions_for_role(effective_role),
            "is_super_admin": is_super_admin,
        }

    def dashboard_summary(self, user: dict) -> dict:
        context = self.current_context(user)
        organization = context.get("organization")
        notification_count = platform_repository.fetch_one(
            "SELECT COUNT(*) AS count FROM notifications WHERE user_id = ?",
            (user["id"],),
        )
        member_count = 0
        usage = {}
        if organization:
            member_row = platform_repository.fetch_one(
                "SELECT COUNT(*) AS count FROM organization_memberships WHERE organization_id = ? AND status = 'active'",
                (organization["id"],),
            )
            member_count = int((member_row or {}).get("count", 0))
            usage = self.usage_for_organization(organization["id"])
        return {
            "context": context,
            "project_count": project_service.project_count(user["id"]),
            "recent_projects": project_service.recent_projects(user["id"], 5),
            "member_count": member_count,
            "notification_count": int((notification_count or {}).get("count", 0)),
            "usage": usage,
        }

    def primary_organization(self, user_id: str) -> dict | None:
        return platform_repository.fetch_one(
            """
            SELECT organizations.*, organization_memberships.role AS membership_role
            FROM organization_memberships
            JOIN organizations ON organizations.id = organization_memberships.organization_id
            WHERE organization_memberships.user_id = ? AND organization_memberships.status = 'active'
            ORDER BY organizations.created_at ASC
            LIMIT 1
            """,
            (user_id,),
        )

    def require_super_admin(self, user: dict) -> None:
        if user.get("role") != "super_admin":
            raise forbidden("Super admin access is required.")

    def require_org_admin(self, user: dict) -> dict:
        org = self.primary_organization(user["id"])
        if user.get("role") == "super_admin" and org:
            return org
        if not org or org.get("membership_role") != "organization_admin":
            raise forbidden("Organization admin access is required.")
        return org

    def permissions_for_role(self, role: str) -> list[str]:
        return SYSTEM_PERMISSIONS.get(role, SYSTEM_PERMISSIONS["viewer"])

    def admin_overview(self) -> dict:
        return {
            "organizations": platform_repository.fetch_one("SELECT COUNT(*) AS count FROM organizations")["count"],
            "users": platform_repository.fetch_one("SELECT COUNT(*) AS count FROM users")["count"],
            "active_subscriptions": platform_repository.fetch_one("SELECT COUNT(*) AS count FROM subscriptions WHERE status = 'active'")["count"],
            "projects": platform_repository.fetch_one("SELECT COUNT(*) AS count FROM projects")["count"],
        }

    def organization_overview(self, user: dict) -> dict:
        org = self.primary_organization(user["id"])
        if not org:
            return {"organization": None, "members": 0, "projects": 0, "usage": None, "subscription": None}
        org_id = org["id"]
        subscription = platform_repository.fetch_one(
            """
            SELECT subscriptions.*, subscription_plans.name AS plan_name, subscription_plans.slug AS plan_slug
            FROM subscriptions
            LEFT JOIN subscription_plans ON subscription_plans.id = subscriptions.plan_id
            WHERE subscriptions.organization_id = ?
            ORDER BY subscriptions.created_at DESC
            LIMIT 1
            """,
            (org_id,),
        )
        return {
            "organization": org,
            "members": platform_repository.fetch_one("SELECT COUNT(*) AS count FROM organization_memberships WHERE organization_id = ? AND status = 'active'", (org_id,))["count"],
            "projects": platform_repository.fetch_one("SELECT COUNT(*) AS count FROM projects WHERE organization_id = ? AND status != 'archived'", (org_id,))["count"],
            "usage": self.usage_for_organization(org_id),
            "subscription": subscription,
        }

    def list_organizations(self) -> list[dict]:
        return platform_repository.fetch_all("SELECT * FROM organizations ORDER BY created_at DESC")

    def create_organization(self, payload: dict, created_by: str | None = None) -> dict:
        now = now_iso()
        org_id = str(uuid4())
        slug_base = slugify(payload["name"])
        slug = slug_base
        index = 1
        while platform_repository.fetch_one("SELECT id FROM organizations WHERE slug = ?", (slug,)):
            index += 1
            slug = f"{slug_base}-{index}"
        plan = platform_repository.fetch_one("SELECT * FROM subscription_plans WHERE slug = ?", (payload.get("plan_slug") or "starter",))
        platform_repository.execute(
            """
            INSERT INTO organizations
            (id, name, slug, status, plan_id, storage_limit_mb, project_limit, user_limit, export_limit_monthly, ai_credit_limit_monthly, created_at, updated_at)
            VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                org_id,
                payload["name"],
                slug,
                plan["id"] if plan else None,
                (plan or {}).get("storage_limit_mb", 1024),
                (plan or {}).get("project_limit", 10),
                (plan or {}).get("user_limit", 5),
                (plan or {}).get("export_limit_monthly", 100),
                (plan or {}).get("ai_credit_limit_monthly", 1000),
                now,
                now,
            ),
        )
        if plan:
            platform_repository.execute(
                """
                INSERT INTO subscriptions
                (id, organization_id, plan_id, status, provider, created_at, updated_at)
                VALUES (?, ?, ?, 'active', 'manual', ?, ?)
                """,
                (str(uuid4()), org_id, plan["id"], now, now),
            )
        admin_email = (payload.get("admin_email") or "").strip().lower()
        if admin_email:
            user = platform_repository.fetch_one("SELECT * FROM users WHERE email = ?", (admin_email,))
            if user:
                user_id = user["id"]
            else:
                user_id = str(uuid4())
                temp_password = token_urlsafe(10) + "Aa1!"
                platform_repository.execute(
                    """
                    INSERT INTO users (id, email, password_hash, full_name, role, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'organization_admin', 'active', ?, ?)
                    """,
                    (user_id, admin_email, hash_password(temp_password), admin_email.split("@")[0], now, now),
                )
            platform_repository.execute("UPDATE users SET role = 'organization_admin' WHERE id = ? AND role != 'super_admin'", (user_id,))
            platform_repository.execute(
                """
                INSERT INTO organization_memberships
                (id, organization_id, user_id, role, status, created_at, updated_at)
                VALUES (?, ?, ?, 'organization_admin', 'active', ?, ?)
                ON CONFLICT(organization_id, user_id) DO NOTHING
                """,
                (str(uuid4()), org_id, user_id, now, now),
            )
        self.audit(created_by, org_id, "organization.created", "organization", org_id, {"name": payload["name"]})
        return platform_repository.get_row("organizations", org_id)

    def update_organization(self, organization_id: str, payload: dict, actor_id: str | None = None) -> dict:
        org = platform_repository.get_row("organizations", organization_id)
        if not org:
            raise not_found("Organization not found.")
        allowed = {"name", "status", "user_limit", "project_limit", "storage_limit_mb", "export_limit_monthly", "ai_credit_limit_monthly"}
        updates = {key: value for key, value in payload.items() if key in allowed and value is not None}
        if payload.get("plan_slug"):
            plan = platform_repository.fetch_one("SELECT * FROM subscription_plans WHERE slug = ?", (payload["plan_slug"],))
            if not plan:
                raise bad_request("Subscription plan not found.")
            updates.update({
                "plan_id": plan["id"],
                "user_limit": plan["user_limit"],
                "project_limit": plan["project_limit"],
                "storage_limit_mb": plan["storage_limit_mb"],
                "export_limit_monthly": plan["export_limit_monthly"],
                "ai_credit_limit_monthly": plan["ai_credit_limit_monthly"],
            })
        if updates:
            updates["updated_at"] = now_iso()
            set_clause = ", ".join(f"{key} = ?" for key in updates)
            platform_repository.execute(f"UPDATE organizations SET {set_clause} WHERE id = ?", (*updates.values(), organization_id))
            self.audit(actor_id, organization_id, "organization.updated", "organization", organization_id, updates)
        return platform_repository.get_row("organizations", organization_id)

    def create_super_admin(self, payload: dict, actor_id: str) -> dict:
        email = payload["email"].strip().lower()
        if platform_repository.fetch_one("SELECT id FROM users WHERE email = ?", (email,)):
            raise bad_request("A user already exists for this email.")
        now = now_iso()
        user_id = str(uuid4())
        platform_repository.execute(
            """
            INSERT INTO users (id, email, password_hash, full_name, role, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'super_admin', 'active', ?, ?)
            """,
            (user_id, email, hash_password(payload["password"]), payload.get("full_name") or "Platform Admin", now, now),
        )
        existing_profile = platform_repository.fetch_one("SELECT user_id FROM user_profiles WHERE user_id = ?", (user_id,))
        if existing_profile:
            platform_repository.execute("UPDATE user_profiles SET full_name = ?, updated_at = ? WHERE user_id = ?", (payload.get("full_name") or "Platform Admin", now, user_id))
        else:
            platform_repository.execute("INSERT INTO user_profiles (user_id, full_name, updated_at) VALUES (?, ?, ?)", (user_id, payload.get("full_name") or "Platform Admin", now))
        platform_org = platform_repository.fetch_one("SELECT id FROM organizations WHERE slug = 'platform'")
        if platform_org:
            platform_repository.execute(
                """
                INSERT INTO organization_memberships
                (id, organization_id, user_id, role, status, created_at, updated_at)
                VALUES (?, ?, ?, 'super_admin', 'active', ?, ?)
                ON CONFLICT(organization_id, user_id) DO NOTHING
                """,
                (str(uuid4()), platform_org["id"], user_id, now, now),
            )
        self.audit(actor_id, platform_org["id"] if platform_org else None, "super_admin.created", "user", user_id, {"email": email})
        return platform_repository.fetch_one("SELECT id, email, full_name, role, status, created_at FROM users WHERE id = ?", (user_id,))

    def list_super_admins(self) -> list[dict]:
        return platform_repository.fetch_all("SELECT id, email, full_name, role, status, created_at, updated_at FROM users WHERE role = 'super_admin' ORDER BY created_at DESC")

    def list_members(self, organization_id: str) -> list[dict]:
        return platform_repository.fetch_all(
            """
            SELECT organization_memberships.*, users.email, users.full_name
            FROM organization_memberships
            JOIN users ON users.id = organization_memberships.user_id
            WHERE organization_memberships.organization_id = ?
            ORDER BY organization_memberships.created_at DESC
            """,
            (organization_id,),
        )

    def invite_member(self, organization_id: str, payload: dict, invited_by: str) -> dict:
        now = now_iso()
        token = token_urlsafe(32)
        invitation = {
            "id": str(uuid4()),
            "organization_id": organization_id,
            "email": payload["email"].strip().lower(),
            "role": payload.get("role") or "member",
            "token_hash": sha256(token.encode()).hexdigest(),
            "status": "pending",
            "invited_by": invited_by,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
            "created_at": now,
        }
        platform_repository.execute(
            """
            INSERT INTO user_invitations
            (id, organization_id, email, role, token_hash, status, invited_by, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tuple(invitation.values()),
        )
        notification_id = str(uuid4())
        platform_repository.execute(
            """
            INSERT INTO notifications (id, organization_id, user_id, channel, recipient, subject, body, status, created_at)
            VALUES (?, ?, ?, 'email', ?, 'Organization invitation', ?, 'queued', ?)
            """,
            (notification_id, organization_id, invited_by, invitation["email"], f"Invitation token: {token}", now),
        )
        self.audit(invited_by, organization_id, "member.invited", "invitation", invitation["id"], {"email": invitation["email"], "role": invitation["role"]})
        invitation["token"] = token
        return invitation

    def system_roles(self) -> list[dict]:
        return [
            {"slug": role, "name": role.replace("_", " ").title(), "permissions": permissions}
            for role, permissions in SYSTEM_PERMISSIONS.items()
        ]

    def list_subscription_plans(self) -> list[dict]:
        plans = platform_repository.fetch_all("SELECT * FROM subscription_plans ORDER BY price_monthly ASC")
        for plan in plans:
            plan["features"] = json.loads(plan.pop("features_json") or "[]")
        return plans

    def create_subscription_plan(self, payload: dict, actor_id: str | None = None) -> dict:
        if platform_repository.fetch_one("SELECT id FROM subscription_plans WHERE slug = ?", (payload["slug"],)):
            raise bad_request("A plan already exists with this slug.")
        now = now_iso()
        plan_id = str(uuid4())
        platform_repository.execute(
            """
            INSERT INTO subscription_plans
            (id, name, slug, price_monthly, currency, user_limit, project_limit, storage_limit_mb, export_limit_monthly,
             ai_credit_limit_monthly, features_json, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                plan_id,
                payload["name"],
                payload["slug"],
                payload["price_monthly"],
                payload["currency"],
                payload["user_limit"],
                payload["project_limit"],
                payload["storage_limit_mb"],
                payload["export_limit_monthly"],
                payload["ai_credit_limit_monthly"],
                json.dumps(payload.get("features") or []),
                now,
                now,
            ),
        )
        self.audit(actor_id, None, "subscription_plan.created", "subscription_plan", plan_id, {"slug": payload["slug"]})
        return platform_repository.get_row("subscription_plans", plan_id)

    def list_billing_history(self, organization_id: str | None = None) -> list[dict]:
        if organization_id:
            return platform_repository.fetch_all("SELECT * FROM billing_history WHERE organization_id = ? ORDER BY created_at DESC", (organization_id,))
        return platform_repository.fetch_all("SELECT * FROM billing_history ORDER BY created_at DESC")

    def record_webhook(self, payload: dict) -> dict:
        now = now_iso()
        event_id = str(uuid4())
        platform_repository.execute(
            """
            INSERT INTO payment_webhook_events (id, provider, event_type, event_id, payload_json, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'received', ?)
            """,
            (event_id, payload["provider"], payload["event_type"], payload.get("event_id"), json.dumps(payload.get("payload") or {}), now),
        )
        return platform_repository.get_row("payment_webhook_events", event_id)




    def list_audit_logs(self, user: dict) -> list[dict]:
        if user.get("role") == "super_admin":
            return platform_repository.fetch_all("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 200")
        org = self.primary_organization(user["id"])
        if not org:
            return []
        return platform_repository.fetch_all("SELECT * FROM audit_logs WHERE organization_id = ? ORDER BY created_at DESC LIMIT 200", (org["id"],))

    def profile(self, user_id: str) -> dict:
        user = platform_repository.fetch_one("SELECT id, email, full_name, role, status, created_at, updated_at FROM users WHERE id = ?", (user_id,))
        profile = platform_repository.fetch_one("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)) or {}
        settings = platform_repository.fetch_one("SELECT settings_json FROM account_settings WHERE user_id = ?", (user_id,))
        return {"user": user, "profile": profile, "settings": json.loads(settings["settings_json"]) if settings else {}}

    def update_profile(self, user_id: str, payload: dict) -> dict:
        now = now_iso()
        allowed = {"full_name", "phone", "job_title", "timezone"}
        values = {key: payload.get(key) for key in allowed if payload.get(key) is not None}
        if values:
            platform_repository.execute(
                """
                INSERT INTO user_profiles (user_id, full_name, phone, job_title, timezone, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    full_name = excluded.full_name,
                    phone = excluded.phone,
                    job_title = excluded.job_title,
                    timezone = excluded.timezone,
                    updated_at = excluded.updated_at
                """,
                (user_id, values.get("full_name"), values.get("phone"), values.get("job_title"), values.get("timezone"), now),
            )
            if values.get("full_name"):
                platform_repository.execute("UPDATE users SET full_name = ?, updated_at = ? WHERE id = ?", (values["full_name"], now, user_id))
        return self.profile(user_id)

    def account_settings(self, user_id: str) -> dict:
        row = platform_repository.fetch_one("SELECT settings_json FROM account_settings WHERE user_id = ?", (user_id,))
        return json.loads(row["settings_json"]) if row else {}

    def update_account_settings(self, user_id: str, settings_payload: dict) -> dict:
        now = now_iso()
        merged = {**self.account_settings(user_id), **settings_payload}
        platform_repository.execute(
            """
            INSERT INTO account_settings (user_id, settings_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET settings_json = excluded.settings_json, updated_at = excluded.updated_at
            """,
            (user_id, json.dumps(merged), now),
        )
        return merged

    def organization_settings(self, organization_id: str) -> dict:
        row = platform_repository.fetch_one("SELECT settings_json FROM organization_settings WHERE organization_id = ?", (organization_id,))
        return json.loads(row["settings_json"]) if row else {}

    def update_organization_settings(self, organization_id: str, settings_payload: dict, actor_id: str | None = None) -> dict:
        now = now_iso()
        merged = {**self.organization_settings(organization_id), **settings_payload}
        platform_repository.execute(
            """
            INSERT INTO organization_settings (organization_id, settings_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(organization_id) DO UPDATE SET settings_json = excluded.settings_json, updated_at = excluded.updated_at
            """,
            (organization_id, json.dumps(merged), now),
        )
        self.audit(actor_id, organization_id, "organization_settings.updated", "organization", organization_id, {})
        return merged

    def usage_for_organization(self, organization_id: str) -> dict:
        period_key = datetime.now(timezone.utc).strftime("%Y-%m")
        usage = platform_repository.fetch_one("SELECT * FROM usage_counters WHERE organization_id = ? AND period_key = ?", (organization_id, period_key))
        org = platform_repository.get_row("organizations", organization_id)
        return {
            "period_key": period_key,
            "usage": usage or {"projects_created": 0, "storage_used_mb": 0, "exports_generated": 0, "ai_credits_used": 0},
            "limits": {
                "projects": org.get("project_limit") if org else 0,
                "storage_mb": org.get("storage_limit_mb") if org else 0,
                "exports_monthly": org.get("export_limit_monthly") if org else 0,
                "ai_credits_monthly": org.get("ai_credit_limit_monthly") if org else 0,
            },
        }

    def list_notifications(self, user: dict) -> list[dict]:
        if user.get("role") == "super_admin":
            return platform_repository.fetch_all("SELECT * FROM notifications ORDER BY created_at DESC LIMIT 100")
        return platform_repository.fetch_all("SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 100", (user["id"],))

    def request_password_reset(self, email: str) -> dict:
        user = platform_repository.fetch_one("SELECT id, email FROM users WHERE email = ?", (email.strip().lower(),))
        if not user:
            return {"status": "ok"}
        token = token_urlsafe(32)
        now = now_iso()
        platform_repository.execute(
            """
            INSERT INTO password_reset_tokens (id, user_id, token_hash, status, expires_at, created_at)
            VALUES (?, ?, ?, 'active', ?, ?)
            """,
            (str(uuid4()), user["id"], sha256(token.encode()).hexdigest(), (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(), now),
        )
        platform_repository.execute(
            """
            INSERT INTO notifications (id, user_id, channel, recipient, subject, body, status, created_at)
            VALUES (?, ?, 'email', ?, 'Password reset', ?, 'queued', ?)
            """,
            (str(uuid4()), user["id"], user["email"], f"Reset token: {token}", now),
        )
        return {"status": "ok", "reset_token": token}

    def audit(self, user_id: str | None, organization_id: str | None, action: str, entity_type: str | None, entity_id: str | None, metadata: dict) -> None:
        platform_repository.execute(
            """
            INSERT INTO audit_logs (id, organization_id, user_id, action, entity_type, entity_id, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (str(uuid4()), organization_id, user_id, action, entity_type, entity_id, json.dumps(metadata), now_iso()),
        )


platform_service = PlatformService()
