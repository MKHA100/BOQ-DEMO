import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from demo_backend.router import router


app = FastAPI(title="AutoBOQ Demo API", version="1.0")
cors_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if origin.strip()]
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
