from fastapi import APIRouter, Depends, Header
from app.auth.auth_schemas import AuthCredentials, AuthResponse, AuthUser
from app.auth.auth_service import auth_service
from app.auth.dependencies import extract_bearer_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
def register(credentials: AuthCredentials):
    return auth_service.register(credentials.email, credentials.password)


@router.post("/login", response_model=AuthResponse)
def login(credentials: AuthCredentials):
    return auth_service.login(credentials.email, credentials.password)


@router.get("/me", response_model=AuthUser)
def me(current_user: dict = Depends(get_current_user)):
    return current_user


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)):
    auth_service.logout(extract_bearer_token(authorization))
    return {"status": "logged_out"}
