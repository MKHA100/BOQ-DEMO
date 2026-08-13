from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from app.auth.dependencies import get_current_user
from app.floor_plans.schemas import (
    FloorCropUpsertRequest,
    FloorPlansState,
    FloorSourceUploadResult,
    FloorUpdateRequest,
    ProjectFloorSettingsUpdate,
)
from app.floor_plans.service import floor_plans_service
from app.projects.project_service import project_service

router = APIRouter(prefix="/projects/{project_id}/floor-plans", tags=["floor-plans"])


def _project(project_id: str, current_user: dict) -> dict:
    return project_service.get_project(project_id, current_user.get("id"))


@router.get("", response_model=FloorPlansState)
def get_floor_plans(project_id: str, current_user: dict = Depends(get_current_user)):
    project = _project(project_id, current_user)
    return floor_plans_service.get_state(project, created_by=current_user.get("id"))


@router.patch("/settings", response_model=FloorPlansState)
def update_floor_settings(
    project_id: str,
    payload: ProjectFloorSettingsUpdate,
    current_user: dict = Depends(get_current_user),
):
    project = _project(project_id, current_user)
    floor_plans_service.update_project_settings(
        project_id,
        height_mm=payload.default_wall_height_mm,
        unit=payload.measurement_unit,
    )
    return floor_plans_service.get_state(project, created_by=current_user.get("id"))


@router.post("/floors", response_model=FloorPlansState)
def add_floor(project_id: str, current_user: dict = Depends(get_current_user)):
    project = _project(project_id, current_user)
    floor_plans_service.add_floor(project_id, created_by=current_user.get("id"))
    return floor_plans_service.get_state(project, created_by=current_user.get("id"))


@router.patch("/floors/{floor_id}", response_model=FloorPlansState)
def update_floor(
    project_id: str,
    floor_id: str,
    payload: FloorUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    project = _project(project_id, current_user)
    floor_plans_service.update_floor(project_id, floor_id, payload.model_dump(exclude_unset=True))
    return floor_plans_service.get_state(project, created_by=current_user.get("id"))


@router.delete("/floors/{floor_id}", response_model=FloorPlansState)
def delete_floor(project_id: str, floor_id: str, current_user: dict = Depends(get_current_user)):
    project = _project(project_id, current_user)
    floor_plans_service.delete_floor(project_id, floor_id)
    return floor_plans_service.get_state(project, created_by=current_user.get("id"))


@router.post("/floors/{floor_id}/source", response_model=FloorSourceUploadResult)
async def upload_floor_source(
    project_id: str,
    floor_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return await floor_plans_service.upload_floor_source(
        project_id=project_id,
        floor_id=floor_id,
        upload=file,
        created_by=current_user.get("id"),
    )


@router.put("/floors/{floor_id}/crop")
def save_floor_crop(
    project_id: str,
    floor_id: str,
    payload: FloorCropUpsertRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floor_plans_service.save_crop(
        project_id=project_id,
        floor_id=floor_id,
        payload=payload.model_dump(),
        created_by=current_user.get("id"),
    )


@router.post("/documents/{document_id}/prepare", response_model=FloorPlansState)
def prepare_document(
    project_id: str,
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    project = _project(project_id, current_user)
    floor_plans_service.prepare_document(
        project_id,
        document_id,
        created_by=current_user.get("id"),
        retry_failed=True,
    )
    return floor_plans_service.get_state(project, created_by=current_user.get("id"))


@router.get("/documents/{document_id}/pages/{page_number}/thumbnail", include_in_schema=False)
def page_thumbnail(
    project_id: str,
    document_id: str,
    page_number: int,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floor_plans_service.asset_response(
        project_id,
        document_id=document_id,
        page_number=page_number,
        asset="thumbnail",
    )


@router.get("/documents/{document_id}/pages/{page_number}/preview", include_in_schema=False)
def page_preview(
    project_id: str,
    document_id: str,
    page_number: int,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floor_plans_service.asset_response(
        project_id,
        document_id=document_id,
        page_number=page_number,
        asset="preview",
    )


@router.get("/floors/{floor_id}/crop-asset", include_in_schema=False)
def floor_crop_asset(project_id: str, floor_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return floor_plans_service.crop_asset_response(project_id, floor_id, "crop")


@router.get("/floors/{floor_id}/preview-asset", include_in_schema=False)
def floor_preview_asset(project_id: str, floor_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return floor_plans_service.crop_asset_response(project_id, floor_id, "preview")
