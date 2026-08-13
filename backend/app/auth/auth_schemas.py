from pydantic import BaseModel, Field


class AuthCredentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class AuthUser(BaseModel):
    id: str
    email: str
    created_at: str
    full_name: str | None = None
    role: str = "member"
    status: str = "active"
    organization_id: str | None = None
    organization_name: str | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser
