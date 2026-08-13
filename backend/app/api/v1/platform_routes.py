from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.platform.platform_schemas import (
    MemberInviteRequest,
    OrganizationCreateRequest,
    OrganizationUpdateRequest,
    PaymentWebhookRequest,
    ProfileUpdateRequest,
    SettingsUpdateRequest,
    SubscriptionPlanRequest,
    SuperAdminCreateRequest,
)
from app.platform.platform_service import platform_service

router = APIRouter(prefix="/platform", tags=["platform"])


@router.get("/me")
def platform_me(current_user: dict = Depends(get_current_user)):
    return platform_service.current_context(current_user)


@router.get("/dashboard-summary")
def dashboard_summary(current_user: dict = Depends(get_current_user)):
    return platform_service.dashboard_summary(current_user)


@router.get("/admin/overview")
def admin_overview(current_user: dict = Depends(get_current_user)):
    platform_service.require_super_admin(current_user)
    return platform_service.admin_overview()


@router.get("/admin/organizations")
def list_organizations(current_user: dict = Depends(get_current_user)):
    platform_service.require_super_admin(current_user)
    return platform_service.list_organizations()


@router.post("/admin/organizations")
def create_organization(payload: OrganizationCreateRequest, current_user: dict = Depends(get_current_user)):
    platform_service.require_super_admin(current_user)
    return platform_service.create_organization(payload.model_dump(), current_user["id"])


@router.patch("/admin/organizations/{organization_id}")
def update_organization(organization_id: str, payload: OrganizationUpdateRequest, current_user: dict = Depends(get_current_user)):
    platform_service.require_super_admin(current_user)
    return platform_service.update_organization(organization_id, payload.model_dump(exclude_unset=True), current_user["id"])


@router.get("/admin/super-admins")
def list_super_admins(current_user: dict = Depends(get_current_user)):
    platform_service.require_super_admin(current_user)
    return platform_service.list_super_admins()


@router.post("/admin/super-admins")
def create_super_admin(payload: SuperAdminCreateRequest, current_user: dict = Depends(get_current_user)):
    platform_service.require_super_admin(current_user)
    return platform_service.create_super_admin(payload.model_dump(), current_user["id"])


@router.get("/admin/subscription-plans")
def list_subscription_plans(current_user: dict = Depends(get_current_user)):
    return platform_service.list_subscription_plans()


@router.post("/admin/subscription-plans")
def create_subscription_plan(payload: SubscriptionPlanRequest, current_user: dict = Depends(get_current_user)):
    platform_service.require_super_admin(current_user)
    return platform_service.create_subscription_plan(payload.model_dump(), current_user["id"])


@router.get("/organization/overview")
def organization_overview(current_user: dict = Depends(get_current_user)):
    return platform_service.organization_overview(current_user)


@router.get("/organization/members")
def organization_members(current_user: dict = Depends(get_current_user)):
    organization = platform_service.require_org_admin(current_user)
    return platform_service.list_members(organization["id"])


@router.post("/organization/invitations")
def invite_member(payload: MemberInviteRequest, current_user: dict = Depends(get_current_user)):
    organization = platform_service.require_org_admin(current_user)
    return platform_service.invite_member(organization["id"], payload.model_dump(), current_user["id"])


@router.get("/organization/roles")
def organization_roles(current_user: dict = Depends(get_current_user)):
    platform_service.require_org_admin(current_user)
    return platform_service.system_roles()


@router.get("/organization/settings")
def get_organization_settings(current_user: dict = Depends(get_current_user)):
    organization = platform_service.require_org_admin(current_user)
    return platform_service.organization_settings(organization["id"])


@router.patch("/organization/settings")
def update_organization_settings(payload: SettingsUpdateRequest, current_user: dict = Depends(get_current_user)):
    organization = platform_service.require_org_admin(current_user)
    return platform_service.update_organization_settings(organization["id"], payload.settings, current_user["id"])





@router.get("/audit-logs")
def audit_logs(current_user: dict = Depends(get_current_user)):
    return platform_service.list_audit_logs(current_user)


@router.get("/billing-history")
def billing_history(current_user: dict = Depends(get_current_user)):
    organization = None if current_user.get("role") == "super_admin" else platform_service.primary_organization(current_user["id"])
    return platform_service.list_billing_history(organization["id"] if organization else None)


@router.post("/payment-webhooks")
def payment_webhook(payload: PaymentWebhookRequest):
    return platform_service.record_webhook(payload.model_dump())


@router.get("/usage")
def usage(current_user: dict = Depends(get_current_user)):
    organization = platform_service.primary_organization(current_user["id"])
    return platform_service.usage_for_organization(organization["id"]) if organization else {}


@router.get("/notifications")
def notifications(current_user: dict = Depends(get_current_user)):
    return platform_service.list_notifications(current_user)


@router.get("/account/profile")
def profile(current_user: dict = Depends(get_current_user)):
    return platform_service.profile(current_user["id"])


@router.patch("/account/profile")
def update_profile(payload: ProfileUpdateRequest, current_user: dict = Depends(get_current_user)):
    return platform_service.update_profile(current_user["id"], payload.model_dump(exclude_unset=True))


@router.get("/account/settings")
def get_account_settings(current_user: dict = Depends(get_current_user)):
    return platform_service.account_settings(current_user["id"])


@router.patch("/account/settings")
def update_account_settings(payload: SettingsUpdateRequest, current_user: dict = Depends(get_current_user)):
    return platform_service.update_account_settings(current_user["id"], payload.settings)


@router.post("/password-reset/request")
def request_password_reset(payload: dict):
    return platform_service.request_password_reset(payload.get("email", ""))
