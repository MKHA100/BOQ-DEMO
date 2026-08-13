from typing import Any
from pydantic import BaseModel, Field


class OrganizationCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    admin_email: str | None = None
    plan_slug: str = "starter"


class OrganizationUpdateRequest(BaseModel):
    name: str | None = None
    status: str | None = None
    plan_slug: str | None = None
    user_limit: int | None = None
    project_limit: int | None = None
    storage_limit_mb: int | None = None
    export_limit_monthly: int | None = None
    ai_credit_limit_monthly: int | None = None


class SuperAdminCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = None


class MemberInviteRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    role: str = "member"


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    job_title: str | None = None
    timezone: str | None = None


class SettingsUpdateRequest(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)



class SubscriptionPlanRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=80)
    price_monthly: float = 0
    currency: str = "USD"
    user_limit: int = 5
    project_limit: int = 10
    storage_limit_mb: int = 1024
    export_limit_monthly: int = 100
    ai_credit_limit_monthly: int = 1000
    features: list[str] = Field(default_factory=list)


class PaymentWebhookRequest(BaseModel):
    provider: str
    event_type: str
    event_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
