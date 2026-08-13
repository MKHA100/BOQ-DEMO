from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth_routes import router as auth_router
from app.api.v1.job_routes import router as job_router
from app.api.v1.platform_routes import router as platform_router
from app.api.v1.project_routes import router as project_router
from app.boq.routes import router as boq_router
from app.core.config import settings
from app.core.performance import add_performance_headers
from app.database.session import get_connection, init_db
from app.floor_plans.routes import router as floor_plans_router
from app.floors.routes import router as floors_router
from app.model_review.routes import router as model_review_router
from app.review.routes import router as review_router
from app.scale.routes import router as scale_router
from app.specifications.routes import router as specifications_router
from app.walls.routes import router as walls_router
from app.workflow.jobs import register_foundation_job_specs
from app.workflow.read_routes import router as workflow_read_router
from app.workflow.routes import router as workflow_router

app = FastAPI(title=settings.app_name, version=settings.app_version)
register_foundation_job_specs()
init_db()
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(add_performance_headers)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/health/ready")
def readiness_check() -> dict:
    with get_connection() as connection:
        connection.execute("SELECT 1").fetchone()
        counts = connection.execute(
            """
            SELECT
              SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending,
              SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) AS running,
              SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed
            FROM job_runs
            """
        ).fetchone()
    return {
        "status": "ready",
        "database": "ready",
        "jobs": {
            "pending": int(counts["pending"] or 0),
            "running": int(counts["running"] or 0),
            "failed": int(counts["failed"] or 0),
        },
    }


for router in (
    auth_router,
    platform_router,
    project_router,
    workflow_router,
    workflow_read_router,
    floor_plans_router,
    specifications_router,
    scale_router,
    model_review_router,
    walls_router,
    floors_router,
    review_router,
    boq_router,
    job_router,
):
    app.include_router(router, prefix=settings.api_prefix)
