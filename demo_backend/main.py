from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from demo_backend.router import router


app = FastAPI(title="AutoBOQ Demo API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mode": "demo"}


app.include_router(router, prefix="/api/v1")
