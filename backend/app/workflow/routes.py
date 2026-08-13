from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.auth.dependencies import get_current_user
from app.projects.project_service import project_service
from app.workflow.schemas import (
    CalibrationUpsertRequest,
    DocumentResponse,
    DocumentUploadResult,
    FloorCropSaveRequest,
    ElementCreateRequest,
    ElementPropertyUpdateRequest,
    ElementRelationCreateRequest,
    FloorCreateRequest,
    FloorResponse,
    MutationResult,
    ProjectWorkflowSummary,
    RoomCreateRequest,
    RoomGeometryUpdateRequest,
    ScheduleFileCreateRequest,
    SpecificationFileCreateRequest,
    WallCreateRequest,
)
from app.workflow.service import workflow_service
from app.workflow.files import workflow_file_service
from app.pdf_upload.service import pdf_upload_service

router = APIRouter(prefix="/projects/{project_id}/workflow", tags=["workflow"])


def _project(project_id: str, current_user: dict) -> dict:
    return project_service.get_project(project_id, current_user.get("id"))


@router.get("/summary", response_model=ProjectWorkflowSummary)
def get_workflow_summary(project_id: str, current_user: dict = Depends(get_current_user)):
    project = _project(project_id, current_user)
    return workflow_service.get_summary(project_id=project_id, project=project)


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(project_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return pdf_upload_service.list_documents(project_id)


@router.post("/documents", response_model=DocumentUploadResult)
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    document_type: str = Form(default="source"),
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    if document_type != "source":
        from app.core.errors import bad_request

        raise bad_request("Only the main construction PDF can be uploaded here.")
    return await pdf_upload_service.upload_main_pdf(
        project_id=project_id,
        upload=file,
        created_by=current_user.get("id"),
    )


@router.post("/floor-crops", response_model=MutationResult)
def save_floor_crop(
    project_id: str,
    payload: FloorCropSaveRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return workflow_file_service.save_floor_crop(
        project_id=project_id,
        payload=payload.model_dump(),
        created_by=current_user.get("id"),
    )


@router.post("/schedule-files", response_model=MutationResult)
def create_schedule_file(
    project_id: str,
    payload: ScheduleFileCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return workflow_file_service.create_schedule_file(
        project_id=project_id,
        payload=payload.model_dump(),
        created_by=current_user.get("id"),
    )


@router.post("/specification-files", response_model=MutationResult)
def create_specification_file(
    project_id: str,
    payload: SpecificationFileCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return workflow_file_service.create_specification_file(
        project_id=project_id,
        payload=payload.model_dump(),
        created_by=current_user.get("id"),
    )


@router.get("/floors", response_model=list[FloorResponse])
def list_floors(project_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return workflow_service.list_floors(project_id)


@router.post("/floors", response_model=FloorResponse)
def create_floor(project_id: str, payload: FloorCreateRequest, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return workflow_service.create_floor(
        project_id=project_id,
        name=payload.name,
        level_index=payload.level_index,
        created_by=current_user.get("id"),
    )


@router.post("/elements", response_model=MutationResult)
def create_element(project_id: str, payload: ElementCreateRequest, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return workflow_service.create_element(
        project_id=project_id,
        payload=payload.model_dump(),
        created_by=current_user.get("id"),
    )


@router.patch("/elements/{element_id}/properties/{property_name}", response_model=MutationResult)
def update_element_property(
    project_id: str,
    element_id: str,
    property_name: str,
    payload: ElementPropertyUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return workflow_service.update_element_property(
        project_id=project_id,
        element_id=element_id,
        property_name=property_name,
        value=payload.value,
        unit=payload.unit,
        source=payload.source,
        confirm=payload.confirm,
        created_by=current_user.get("id"),
    )


@router.post("/walls", response_model=MutationResult)
def create_wall(project_id: str, payload: WallCreateRequest, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return workflow_service.create_wall(
        project_id=project_id,
        payload=payload.model_dump(),
        created_by=current_user.get("id"),
    )


@router.post("/element-relations", response_model=MutationResult)
def create_element_relation(
    project_id: str,
    payload: ElementRelationCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return workflow_service.create_relation(
        project_id=project_id,
        payload=payload.model_dump(),
        created_by=current_user.get("id"),
    )


@router.put("/floors/{floor_id}/calibration", response_model=MutationResult)
def save_calibration(
    project_id: str,
    floor_id: str,
    payload: CalibrationUpsertRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return workflow_service.save_calibration(
        project_id=project_id,
        floor_id=floor_id,
        point_a=payload.point_a.model_dump(),
        point_b=payload.point_b.model_dump(),
        real_distance=payload.real_distance,
        unit=payload.unit,
        source_crop_version=payload.source_crop_version,
        confirmed_by=current_user.get("id"),
    )


@router.post("/rooms", response_model=MutationResult)
def create_room(project_id: str, payload: RoomCreateRequest, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return workflow_service.create_room(
        project_id=project_id,
        payload=payload.model_dump(),
        created_by=current_user.get("id"),
    )


@router.patch("/rooms/{room_id}/geometry", response_model=MutationResult)
def update_room_geometry(
    project_id: str,
    room_id: str,
    payload: RoomGeometryUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return workflow_service.update_room_geometry(
        project_id=project_id,
        room_id=room_id,
        geometry=payload.geometry,
        confirm=payload.confirm,
        created_by=current_user.get("id"),
    )
