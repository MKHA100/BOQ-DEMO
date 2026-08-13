from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.auth.dependencies import get_current_user
from app.projects.project_service import project_service
from app.specifications.schemas import (
    Category,
    CategorySkipRequest,
    CropSourceRequest,
    SourceScopeUpdate,
    SpecificationsState,
)
from app.specifications.service import specifications_service

router = APIRouter(prefix="/projects/{project_id}/specifications", tags=["specifications"])


def _project(project_id: str, current_user: dict) -> dict:
    return project_service.get_project(project_id, current_user.get("id"))


def _floor_ids(value: str) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        parsed = []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


@router.get("", response_model=SpecificationsState)
def get_specifications(project_id: str, current_user: dict = Depends(get_current_user)):
    project = _project(project_id, current_user)
    return specifications_service.get_state(project)


@router.post("/sources/upload")
async def upload_source(
    project_id: str,
    category: Category = Form(...),
    scope_mode: str = Form("all"),
    floor_ids: str = Form("[]"),
    replace_source_id: str | None = Form(default=None),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    project = _project(project_id, current_user)
    source = await specifications_service.upload_source(
        project_id=project_id,
        category=category,
        upload=file,
        scope_mode=scope_mode,
        floor_ids=_floor_ids(floor_ids),
        replace_source_id=replace_source_id,
        created_by=current_user.get("id"),
    )
    return {"source_id": source["id"], "state": specifications_service.get_state(project)}


@router.post("/sources/crop")
def create_crop_source(
    project_id: str,
    payload: CropSourceRequest,
    current_user: dict = Depends(get_current_user),
):
    project = _project(project_id, current_user)
    source = specifications_service.create_crop_source(
        project_id=project_id,
        payload=payload.model_dump(),
        created_by=current_user.get("id"),
    )
    return {"source_id": source["id"], "state": specifications_service.get_state(project)}


@router.patch("/sources/{source_id}/scope")
def update_source_scope(
    project_id: str,
    source_id: str,
    payload: SourceScopeUpdate,
    current_user: dict = Depends(get_current_user),
):
    project = _project(project_id, current_user)
    specifications_service.update_scope(project_id, source_id, payload.scope_mode, payload.floor_ids)
    return specifications_service.get_state(project)


@router.delete("/sources/{source_id}")
def delete_source(project_id: str, source_id: str, current_user: dict = Depends(get_current_user)):
    project = _project(project_id, current_user)
    specifications_service.remove_source(project_id, source_id)
    return specifications_service.get_state(project)


@router.post("/categories/{category}/skip")
def skip_category(
    project_id: str,
    category: Category,
    payload: CategorySkipRequest,
    current_user: dict = Depends(get_current_user),
):
    project = _project(project_id, current_user)
    specifications_service.skip_category(project_id, category, payload.skipped)
    return specifications_service.get_state(project)


@router.get("/sources/{source_id}/preview", include_in_schema=False)
def source_preview(project_id: str, source_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return specifications_service.source_asset_response(project_id, source_id)
