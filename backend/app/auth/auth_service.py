from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re
from secrets import token_urlsafe
from uuid import uuid4
from app.auth.auth_repository import AuthRepository
from app.auth.passwords import hash_password, verify_password
from app.core.config import settings
from app.core.errors import bad_request, unauthorized

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthService:
    def __init__(self) -> None:
        self.repository = AuthRepository()

    def register(self, email: str, password: str) -> dict:
        normalized_email = self._normalize_email(email)
        if self.repository.get_user_by_email(normalized_email):
            raise bad_request("An account already exists for this email.")
        now = datetime.now(timezone.utc).isoformat()
        user_id = str(uuid4())
        organization_id = str(uuid4())
        user = self.repository.create_user(
            {
                "id": user_id,
                "email": normalized_email,
                "password_hash": hash_password(password),
                "full_name": normalized_email.split("@")[0],
                "role": "organization_admin",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
        )
        from app.platform.platform_repository import platform_repository
        org_name = normalized_email.split("@")[0].replace(".", " ").title() or "Organization"
        org_slug = self._organization_slug(normalized_email)
        platform_repository.execute(
            """
            INSERT INTO organizations
            (id, name, slug, status, storage_limit_mb, project_limit, user_limit, export_limit_monthly, ai_credit_limit_monthly, created_at, updated_at)
            VALUES (?, ?, ?, 'active', 1024, 10, 5, 100, 1000, ?, ?)
            """,
            (organization_id, org_name, org_slug, now, now),
        )
        platform_repository.execute(
            """
            INSERT INTO organization_memberships
            (id, organization_id, user_id, role, status, created_at, updated_at)
            VALUES (?, ?, ?, 'organization_admin', 'active', ?, ?)
            """,
            (str(uuid4()), organization_id, user_id, now, now),
        )
        user["organization_id"] = organization_id
        user["organization_name"] = org_name
        return self._issue_token(user)

    def login(self, email: str, password: str) -> dict:
        normalized_email = self._normalize_email(email)
        user = self.repository.get_user_by_email(normalized_email)
        if not user or not verify_password(password, user["password_hash"]):
            raise unauthorized("Invalid email or password.")
        return self._issue_token(user)

    def get_user_from_token(self, token: str) -> dict:
        token_hash = self._hash_token(token)
        now = datetime.now(timezone.utc).isoformat()
        user = self.repository.get_session_user(token_hash, now)
        if not user:
            raise unauthorized("Authentication is required.")
        return user

    def logout(self, token: str) -> None:
        self.repository.delete_session(self._hash_token(token))

    def _issue_token(self, user: dict) -> dict:
        token = token_urlsafe(40)
        now_dt = datetime.now(timezone.utc)
        expires_at = now_dt + timedelta(hours=settings.auth_token_ttl_hours)
        self.repository.create_session(self._hash_token(token), user["id"], now_dt.isoformat(), expires_at.isoformat())
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "created_at": user["created_at"],
                "full_name": user.get("full_name"),
                "role": user.get("role") or "member",
                "status": user.get("status") or "active",
                "organization_id": user.get("organization_id"),
                "organization_name": user.get("organization_name"),
            },
        }

    def _normalize_email(self, email: str) -> str:
        normalized_email = email.strip().lower()
        if not EMAIL_PATTERN.match(normalized_email):
            raise bad_request("Enter a valid email address.")
        return normalized_email

    def _organization_slug(self, email: str) -> str:
        import re
        base = email.split("@")[0] or "organization"
        return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") + "-org"

    def _hash_token(self, token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()


auth_service = AuthService()
