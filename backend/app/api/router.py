from fastapi import APIRouter
from app.api.v1.auth_routes import router as auth_router
from app.api.v1.platform_routes import router as platform_router
from app.api.v1.project_routes import router as project_router
from app.api.v1.job_routes import router as job_router
from app.workflow.routes import router as workflow_router
from app.workflow.read_routes import router as workflow_read_router
from app.floor_plans.routes import router as floor_plans_router
from app.specifications.routes import router as specifications_router
from app.scale.routes import router as scale_router
from app.model_review.routes import router as model_review_router
from app.walls.routes import router as walls_router
from app.floors.routes import router as floors_router
from app.review.routes import router as review_router
from app.boq.routes import router as boq_router
api_router = APIRouter()
for router in (auth_router, platform_router, project_router, workflow_router, workflow_read_router, floor_plans_router, specifications_router, scale_router, model_review_router, walls_router, floors_router, review_router, boq_router, job_router): api_router.include_router(router)
