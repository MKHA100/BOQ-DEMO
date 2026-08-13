from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_current_user
from app.projects.project_schemas import (
    ProjectCreateRequest,
    ProjectCreateResponse,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.projects.project_service import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectCreateResponse)
def create_project(payload: ProjectCreateRequest, current_user: dict = Depends(get_current_user)):
    project = project_service.create_project(payload.model_dump(), current_user["id"])
    return {**project, "project_id": project["id"]}


@router.get("", response_model=ProjectListResponse)
def list_projects(
    search: str | None = Query(default=None, max_length=120),
    status: str | None = Query(default=None),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    projects, total = project_service.search_projects(
        current_user["id"],
        search=search,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {"projects": projects, "total": total, "limit": limit, "offset": offset}


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, current_user: dict = Depends(get_current_user)):
    return project_service.get_project(project_id, current_user["id"])


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    payload: ProjectUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    return project_service.update_project(
        project_id,
        payload.model_dump(exclude_unset=True),
        current_user["id"],
    )


@router.delete("/{project_id}")
def delete_project(project_id: str, current_user: dict = Depends(get_current_user)):
    project_service.delete_project(project_id, current_user["id"])
    return {"status": "deleted"}
