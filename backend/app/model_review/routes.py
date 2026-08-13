from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.model_review.schemas import BulkConfirmRequest, DetectionAnalysisRequest, ElementCreateRequest, ElementUpdateRequest, PropertyUpdateRequest, ScheduleAssignRequest
from app.model_review.service import model_review_service
from app.projects.project_service import project_service

router = APIRouter(prefix="/projects/{project_id}/model-review", tags=["model-review"])


@router.get("")
def get_state(project_id: str, floor_id: str | None = None, current_user: dict = Depends(get_current_user)):
    project = project_service.get_project(project_id,current_user.get("id"))
    return model_review_service.get_state(project,floor_id)


@router.post("/floors/{floor_id}/elements")
def create_element(project_id: str,floor_id: str,payload: ElementCreateRequest,current_user: dict = Depends(get_current_user)):
    project_service.get_project(project_id,current_user.get("id"))
    return model_review_service.create(project_id=project_id,floor_id=floor_id,payload=payload.model_dump(),created_by=current_user.get("id"))


@router.patch("/floors/{floor_id}/elements/{element_id}")
def update_element(project_id: str,floor_id: str,element_id: str,payload: ElementUpdateRequest,current_user: dict = Depends(get_current_user)):
    project_service.get_project(project_id,current_user.get("id"))
    return model_review_service.update(project_id=project_id,floor_id=floor_id,element_id=element_id,payload=payload.model_dump(exclude_unset=True),created_by=current_user.get("id"))


@router.patch("/floors/{floor_id}/elements/{element_id}/properties/{property_name}")
def update_property(project_id: str,floor_id: str,element_id: str,property_name: str,payload: PropertyUpdateRequest,current_user: dict = Depends(get_current_user)):
    project_service.get_project(project_id,current_user.get("id"))
    return model_review_service.update_property(project_id=project_id,floor_id=floor_id,element_id=element_id,property_name=property_name,value=payload.value,unit=payload.unit,confirm=payload.confirm,created_by=current_user.get("id"))


@router.put("/floors/{floor_id}/elements/{element_id}/schedule")
def assign_schedule(project_id: str,floor_id: str,element_id: str,payload: ScheduleAssignRequest,current_user: dict = Depends(get_current_user)):
    project_service.get_project(project_id,current_user.get("id"))
    return model_review_service.assign_schedule(project_id=project_id,floor_id=floor_id,element_id=element_id,schedule_entry_id=payload.schedule_entry_id,created_by=current_user.get("id"))


@router.post("/floors/{floor_id}/confirm")
def confirm_many(project_id: str,floor_id: str,payload: BulkConfirmRequest,current_user: dict = Depends(get_current_user)):
    project_service.get_project(project_id,current_user.get("id"))
    return model_review_service.confirm_many(project_id=project_id,floor_id=floor_id,element_ids=payload.element_ids,created_by=current_user.get("id"))


@router.post("/floors/{floor_id}/analyze")
def analyze_floor(project_id: str, floor_id: str, payload: DetectionAnalysisRequest, current_user: dict = Depends(get_current_user)):
    project_service.get_project(project_id, current_user.get("id"))
    return model_review_service.analyze_floor(
        project_id=project_id, floor_id=floor_id, analysis_mode=payload.analysis_mode, created_by=current_user.get("id")
    )
