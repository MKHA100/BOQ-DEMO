from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_current_user
from app.projects.project_service import project_service
from app.workflow.read_service import workflow_read_service

router = APIRouter(prefix="/projects/{project_id}/workflow", tags=["workflow"])


def _project(project_id: str, current_user: dict) -> None:
    project_service.get_project(project_id, current_user.get("id"))


@router.get("/documents/{document_id}/pages")
def list_document_pages(project_id: str, document_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return workflow_read_service.list_document_pages(project_id, document_id)


@router.get("/extractions")
def list_extraction_records(
    project_id: str,
    document_id: str | None = None,
    extraction_type: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return workflow_read_service.list_extraction_records(
        project_id,
        document_id=document_id,
        extraction_type=extraction_type,
    )


@router.get("/floors/{floor_id}/crop")
def get_floor_crop(project_id: str, floor_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return workflow_read_service.get_current_crop(project_id, floor_id)


@router.get("/floors/{floor_id}/calibration")
def get_floor_calibration(project_id: str, floor_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return workflow_read_service.get_calibration(project_id, floor_id)


@router.get("/schedule-files")
def list_schedule_files(
    project_id: str,
    floor_id: str | None = None,
    schedule_type: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return workflow_read_service.list_schedule_files(project_id, floor_id=floor_id, schedule_type=schedule_type)


@router.get("/specification-files")
def list_specification_files(
    project_id: str,
    floor_id: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return workflow_read_service.list_specification_files(project_id, floor_id=floor_id)


@router.get("/floors/{floor_id}/elements")
def list_elements(
    project_id: str,
    floor_id: str,
    element_type: str | None = None,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return workflow_read_service.list_elements(
        project_id,
        floor_id,
        element_type=element_type,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/floors/{floor_id}/walls")
def list_walls(
    project_id: str,
    floor_id: str,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return workflow_read_service.list_walls(project_id, floor_id, status=status, limit=limit, offset=offset)


@router.get("/floors/{floor_id}/rooms")
def list_rooms(
    project_id: str,
    floor_id: str,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return workflow_read_service.list_rooms(project_id, floor_id, status=status, limit=limit, offset=offset)


@router.get("/review-issues")
def list_review_issues(
    project_id: str,
    floor_id: str | None = None,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return workflow_read_service.list_review_issues(
        project_id,
        floor_id=floor_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/quantities")
def list_quantities(
    project_id: str,
    floor_id: str | None = None,
    entity_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return workflow_read_service.list_quantities(
        project_id,
        floor_id=floor_id,
        entity_type=entity_type,
        limit=limit,
        offset=offset,
    )


@router.get("/boq")
def get_boq_view(
    project_id: str,
    floor_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return workflow_read_service.get_boq_view(project_id, floor_id=floor_id, limit=limit, offset=offset)
