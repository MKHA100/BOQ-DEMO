import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from demo_backend.router import router


app = FastAPI(title="AutoBOQ Demo API", version="1.0")


def _cors_origin(value: str) -> str:
    """Normalize dashboard-entered origins before Starlette compares them.

    Browsers send origins without a trailing slash, while hosting dashboards
    commonly accept and preserve one. CORS comparisons are exact, so retaining
    that slash turns an otherwise valid browser upload into a failed preflight.
    """
    return value.strip().rstrip("/")


cors_origins = [
    _cors_origin(origin)
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if _cors_origin(origin)
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=os.getenv("CORS_ORIGIN_REGEX") or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mode": "demo"}


app.include_router(router, prefix="/api/v1")
