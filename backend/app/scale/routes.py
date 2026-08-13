from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.projects.project_service import project_service
from app.scale.schemas import CalibrationSaveRequest, CopyCalibrationRequest
from app.scale.service import scale_service

router = APIRouter(prefix="/projects/{project_id}/scale", tags=["scale"])


@router.get("")
def get_scale_state(project_id: str, current_user: dict = Depends(get_current_user)):
    project = project_service.get_project(project_id, current_user.get("id"))
    return scale_service.get_state(project)


@router.put("/floors/{floor_id}")
def save_floor_calibration(
    project_id: str,
    floor_id: str,
    payload: CalibrationSaveRequest,
    current_user: dict = Depends(get_current_user),
):
    project_service.get_project(project_id, current_user.get("id"))
    return scale_service.save(
        project_id=project_id,
        floor_id=floor_id,
        payload=payload.model_dump(),
        confirmed_by=current_user.get("id"),
    )


@router.post("/floors/{floor_id}/copy")
def copy_floor_calibration(
    project_id: str,
    floor_id: str,
    payload: CopyCalibrationRequest,
    current_user: dict = Depends(get_current_user),
):
    project_service.get_project(project_id, current_user.get("id"))
    return scale_service.copy(
        project_id=project_id,
        floor_id=floor_id,
        source_floor_id=payload.source_floor_id,
        confirm=payload.confirm,
        confirmed_by=current_user.get("id"),
    )
