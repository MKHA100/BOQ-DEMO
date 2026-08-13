from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.boq.repo import boq_repository
from app.boq.schemas import (
    BoqDocumentSetupUpdate, BoqRowUpdate, BoqViewRequest, ExportRequest,
    ManualRowCreate, TemplateDuplicateRequest, TemplateItemCreate,
    TemplateItemUpdate, TemplatePackageCreate, TemplatePackageUpdate,
    TemplatePreviewRequest, TemplateSelectRequest,
)
from app.boq.service import boq_service
from app.boq.setup_service import boq_setup_service
from app.boq.template_service import boq_template_service
from app.core.errors import not_found
from app.projects.project_service import project_service
from app.storage.storage_service import storage_service

router = APIRouter(prefix="/projects/{project_id}/boq", tags=["boq"])


def _project(project_id: str, user: dict) -> dict:
    return project_service.get_project(project_id, user.get("id"))


@router.get("")
def state(project_id: str, floor_id: str | None = None, grouping_mode: str = "item", current_user: dict = Depends(get_current_user)):
    return boq_service.state(_project(project_id, current_user), floor_id, grouping_mode)


@router.post("/refresh")
def refresh(project_id: str, payload: BoqViewRequest, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return boq_service.refresh(project_id, current_user.get("id"), payload.grouping_mode)


@router.get("/setup")
def get_setup(project_id: str, current_user: dict = Depends(get_current_user)):
    return boq_setup_service.get(_project(project_id, current_user))


@router.put("/setup")
def update_setup(project_id: str, payload: BoqDocumentSetupUpdate, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    setup = boq_setup_service.update(project_id, payload.model_dump(), current_user.get("id"))
    project = project_service.get_project(project_id, current_user.get("id"))
    state = boq_service.state(project)
    return {"setup": setup, "job": next((job for job in state["active_jobs"] if job.get("category") == "boq"), None)}


@router.get("/templates")
def template_library(project_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return boq_template_service.library(project_id)


@router.post("/templates")
def create_template(project_id: str, payload: TemplatePackageCreate, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return boq_template_service.create_package(project_id, payload.model_dump())


@router.patch("/templates/{template_id}")
def update_template(project_id: str, template_id: str, payload: TemplatePackageUpdate, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return boq_template_service.update_package(project_id, template_id, payload.model_dump(exclude_unset=True))


@router.delete("/templates/{template_id}")
def delete_template(project_id: str, template_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    boq_template_service.delete_package(project_id, template_id)
    return {"deleted": True}


@router.post("/templates/{template_id}/duplicate")
def duplicate_template(project_id: str, template_id: str, payload: TemplateDuplicateRequest, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return boq_template_service.duplicate_package(project_id, template_id, payload.name)


@router.post("/templates/{template_id}/select")
def select_template_package(project_id: str, template_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return boq_service.select_template(project_id, template_id, current_user.get("id"))


@router.post("/template")
def select_template_compat(project_id: str, payload: TemplateSelectRequest, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return boq_service.select_template(project_id, payload.template_id, current_user.get("id"))


@router.post("/templates/{template_id}/items")
def create_template_item(project_id: str, template_id: str, payload: TemplateItemCreate, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return boq_template_service.create_item(project_id, template_id, payload.model_dump())


@router.patch("/templates/{template_id}/items/{item_id}")
def update_template_item(project_id: str, template_id: str, item_id: str, payload: TemplateItemUpdate, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return boq_template_service.update_item(project_id, template_id, item_id, payload.model_dump(exclude_unset=True))


@router.delete("/templates/{template_id}/items/{item_id}")
def delete_template_item(project_id: str, template_id: str, item_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    boq_template_service.delete_item(project_id, template_id, item_id)
    return {"deleted": True}


@router.post("/templates/{template_id}/items/{item_id}/preview")
def preview_template_item(project_id: str, template_id: str, item_id: str, payload: TemplatePreviewRequest, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return boq_template_service.preview(project_id, template_id, item_id, payload.values)


@router.post("/rows")
def add_manual(project_id: str, payload: ManualRowCreate, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return boq_service.add_manual(project_id, payload.model_dump(), current_user.get("id"))


@router.patch("/rows/{row_id}")
def update_row(project_id: str, row_id: str, payload: BoqRowUpdate, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return boq_service.update_row(project_id, row_id, payload.model_dump(exclude_unset=True), current_user.get("id"))


@router.get("/exports")
def list_exports(project_id: str, current_user: dict = Depends(get_current_user)):
    project = _project(project_id, current_user)
    state = boq_service.state(project)
    return {"exports": state["exports"], "active_jobs": state["active_jobs"]}


@router.post("/exports")
def create_export(project_id: str, payload: ExportRequest, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return boq_service.request_export(project_id, payload.model_dump(), current_user.get("id"))


@router.get("/exports/{export_id}/download")
def download(project_id: str, export_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    record = boq_repository.get_export(project_id, export_id)
    if not record or record.get("status") != "ready" or not record.get("object_key"):
        raise not_found("Export is not ready.")
    return storage_service.download_response(
        storage_service.key_to_path(record["object_key"]), filename=record.get("filename")
    )
