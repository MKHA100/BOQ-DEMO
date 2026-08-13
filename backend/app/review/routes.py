from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_user
from app.projects.project_service import project_service
from app.review.schemas import ConfirmRequest, ReviewFieldUpdate
from app.review.service import review_service

router = APIRouter(prefix="/projects/{project_id}/review", tags=["review"])

@router.get("")
def state(project_id: str, floor_id: str | None = None, category: str = "all", current_user: dict = Depends(get_current_user)):
    return review_service.state(project_service.get_project(project_id, current_user.get("id")), floor_id, category)

@router.patch("/items/{item_id}")
def update(project_id: str, item_id: str, payload: ReviewFieldUpdate, current_user: dict = Depends(get_current_user)):
    project_service.get_project(project_id, current_user.get("id")); return review_service.update_field(project_id, item_id, payload.field, payload.value, current_user.get("id"))

@router.post("/confirm")
def confirm(project_id: str, payload: ConfirmRequest, current_user: dict = Depends(get_current_user)):
    project_service.get_project(project_id, current_user.get("id")); return review_service.confirm(project_id, payload.item_ids, payload.scope, payload.floor_id, current_user.get("id"))
