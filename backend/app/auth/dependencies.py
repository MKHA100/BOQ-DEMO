from __future__ import annotations

from fastapi import Header, Request

from app.auth.auth_service import auth_service
from app.core.config import settings
from app.core.errors import unauthorized


LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _development_user() -> dict:
    # id=None intentionally disables ownership filtering in local development.
    # This prevents existing Neon/local projects from disappearing during local testing
    # when the browser token is missing, expired, or belongs to a different test user.
    return {
        "id": None,
        "email": "local@construction.local",
        "full_name": "Local User",
        "role": "local_development",
        "status": "active",
        "organization_id": None,
        "organization_name": "Local Development",
    }


def _hostname(value: str | None) -> str:
    if not value:
        return ""
    host = value.replace("http://", "").replace("https://", "")
    return host.split("/")[0].split(":")[0].strip().lower()


def _is_local_request(request: Request) -> bool:
    host = _hostname(request.headers.get("host"))
    origin = _hostname(request.headers.get("origin"))
    referer = _hostname(request.headers.get("referer"))
    client_host = (request.client.host if request.client else "").strip().lower()
    return any(value in LOCAL_HOSTS for value in (host, origin, referer, client_host))


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise unauthorized("Please sign in to continue.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise unauthorized("Please sign in to continue.")
    return token


def get_current_user(request: Request, authorization: str | None = Header(default=None)) -> dict:
    if settings.allow_local_auth_bypass and _is_local_request(request):
        return _development_user()

    if not settings.auth_required:
        if not authorization:
            return _development_user()
        try:
            return auth_service.get_user_from_token(extract_bearer_token(authorization))
        except Exception:
            return _development_user()

    return auth_service.get_user_from_token(extract_bearer_token(authorization))
