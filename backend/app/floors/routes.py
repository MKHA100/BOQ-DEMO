from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.floors.schemas import (
    FinishZoneCreateRequest,
    RoomCreateRequest,
    RoomCutoutCreateRequest,
    RoomExcludeRequest,
    RoomGeometryPatchRequest,
    RoomMergeRequest,
    RoomSplitLineRequest,
    RoomSplitRequest,
    RoomSuggestionAcceptRequest,
    RoomUpdateRequest,
)
from app.floors.service import floors_service
from app.floors.repo import floors_repository
from app.projects.project_service import project_service

router = APIRouter(prefix="/projects/{project_id}/floors", tags=["floors"])


def _project(project_id: str, current_user: dict) -> dict:
    return project_service.get_project(project_id, current_user.get("id"))


@router.get("")
def state(
    project_id: str,
    floor_id: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    return floors_service.get_state(_project(project_id, current_user), floor_id)


@router.post("/floors/{floor_id}/analyze")
def analyze(project_id: str, floor_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return floors_service.analyze(project_id, floor_id, current_user.get("id"))


@router.post("/floors/{floor_id}/recalculate")
def recalculate(project_id: str, floor_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return floors_service.recalculate(project_id, floor_id, current_user.get("id"))


@router.post("/floors/{floor_id}/confirm-all")
def confirm_all(project_id: str, floor_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return floors_service.confirm_all(project_id, floor_id, current_user.get("id"))


@router.post("/floors/{floor_id}/rooms")
def create(
    project_id: str,
    floor_id: str,
    payload: RoomCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.create(project_id, floor_id, payload.model_dump(), current_user.get("id"))


@router.patch("/floors/{floor_id}/rooms/{room_id}")
def update(
    project_id: str,
    floor_id: str,
    room_id: str,
    payload: RoomUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.update(
        project_id,
        floor_id,
        room_id,
        payload.model_dump(exclude_unset=True),
        current_user.get("id"),
    )


@router.delete("/floors/{floor_id}/rooms/{room_id}")
def delete(
    project_id: str,
    floor_id: str,
    room_id: str,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.delete(project_id, floor_id, room_id, current_user.get("id"))


@router.post("/floors/{floor_id}/rooms/{room_id}/confirm")
def confirm(
    project_id: str,
    floor_id: str,
    room_id: str,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.confirm(project_id, floor_id, room_id, current_user.get("id"))


@router.post("/floors/{floor_id}/rooms/{room_id}/exclude")
def exclude(
    project_id: str,
    floor_id: str,
    room_id: str,
    payload: RoomExcludeRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.exclude(
        project_id, floor_id, room_id, payload.reason, current_user.get("id")
    )


@router.post("/floors/{floor_id}/rooms/{room_id}/split")
def split(
    project_id: str,
    floor_id: str,
    room_id: str,
    payload: RoomSplitRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.split(
        project_id, floor_id, room_id, payload.axis, payload.ratio, current_user.get("id")
    )


@router.post("/floors/{floor_id}/rooms/{room_id}/split-line")
def split_line(
    project_id: str, floor_id: str, room_id: str, payload: RoomSplitLineRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.split_with_line(
        project_id, floor_id, room_id, [point.model_dump() for point in payload.points], current_user.get("id")
    )


@router.post("/floors/{floor_id}/rooms/{room_id}/snap")
def snap_room(
    project_id: str, floor_id: str, room_id: str, current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.snap_to_walls(project_id, floor_id, room_id, current_user.get("id"))


@router.post("/floors/{floor_id}/rooms/{room_id}/finish-zones")
def create_finish_zone(
    project_id: str, floor_id: str, room_id: str, payload: FinishZoneCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.create_finish_zone(
        project_id, floor_id, room_id, payload.model_dump(), current_user.get("id")
    )


@router.patch("/floors/{floor_id}/rooms/{room_id}/finish-zones/{zone_id}")
def update_finish_zone(
    project_id: str, floor_id: str, room_id: str, zone_id: str, payload: RoomUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    data = payload.model_dump(exclude_unset=True)
    if payload.points is not None:
        data["points"] = [point.model_dump() for point in payload.points]
    return floors_service.update_finish_zone(
        project_id, floor_id, room_id, zone_id, data, current_user.get("id")
    )


@router.delete("/floors/{floor_id}/rooms/{room_id}/finish-zones/{zone_id}")
def delete_finish_zone(
    project_id: str, floor_id: str, room_id: str, zone_id: str,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.delete_finish_zone(
        project_id, floor_id, room_id, zone_id, current_user.get("id")
    )


@router.post("/floors/{floor_id}/rooms/{room_id}/merge")
def merge(
    project_id: str,
    floor_id: str,
    room_id: str,
    payload: RoomMergeRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.merge(
        project_id,
        floor_id,
        room_id,
        payload.other_room_id,
        current_user.get("id"),
    )


@router.post("/floors/{floor_id}/rooms/{room_id}/restore")
def restore(
    project_id: str,
    floor_id: str,
    room_id: str,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.restore(project_id, floor_id, room_id, current_user.get("id"))


@router.post("/floors/{floor_id}/precision")
def precision(
    project_id: str,
    floor_id: str,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.precision_refine(project_id, floor_id)


@router.post("/floors/{floor_id}/precision-refine")
def precision_refine(
    project_id: str,
    floor_id: str,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.request_precision(project_id, floor_id, current_user.get("id"))


@router.post("/floors/{floor_id}/interpret")
def interpret_floor(
    project_id: str,
    floor_id: str,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.request_interpretation(project_id, floor_id, current_user.get("id"))


@router.get("/floors/{floor_id}/interpretation-status")
def interpretation_status(
    project_id: str,
    floor_id: str,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.interpretation_status(project_id, floor_id)


@router.get("/floors/{floor_id}/rooms/{room_id}/auto-fix-preview")
def auto_fix_room_preview(project_id: str, floor_id: str, room_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return floors_service.auto_fix_preview(project_id, floor_id, room_id)


@router.post("/floors/{floor_id}/rooms/{room_id}/auto-fix")
def auto_fix_room(project_id: str, floor_id: str, room_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return floors_service.auto_fix(project_id, floor_id, room_id, current_user.get("id"))


@router.post("/floors/{floor_id}/rooms/{room_id}/reset-to-model")
def reset_room_to_model(project_id: str, floor_id: str, room_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return floors_service.reset_to_model(project_id, floor_id, room_id, current_user.get("id"))


@router.post("/floors/{floor_id}/rooms/{room_id}/reset-to-corrected")
def reset_room_to_corrected(project_id: str, floor_id: str, room_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return floors_service.reset_to_corrected(project_id, floor_id, room_id, current_user.get("id"))


@router.get("/floors/{floor_id}/suggestions")
def room_suggestions(project_id: str, floor_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return {"items": floors_repository.list_suggestions(project_id, floor_id)}


@router.post("/floors/{floor_id}/rooms/{room_id}/simplify")
def simplify_room(project_id: str, floor_id: str, room_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return floors_service.simplify_room(project_id, floor_id, room_id, current_user.get("id"))


@router.post("/floors/{floor_id}/rooms/{room_id}/make-rectangle")
def make_rectangle(project_id: str, floor_id: str, room_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return floors_service.make_rectangle(project_id, floor_id, room_id, current_user.get("id"))


@router.post("/floors/{floor_id}/rooms/{room_id}/straighten")
def straighten_room(project_id: str, floor_id: str, room_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return floors_service.straighten_room(project_id, floor_id, room_id, current_user.get("id"))


@router.post("/floors/{floor_id}/rooms/{room_id}/snap-to-walls")
def snap_room_precise(project_id: str, floor_id: str, room_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return floors_service.snap_to_walls(project_id, floor_id, room_id, current_user.get("id"))


@router.patch("/floors/{floor_id}/rooms/{room_id}/geometry")
def patch_room_geometry(
    project_id: str,
    floor_id: str,
    room_id: str,
    payload: RoomGeometryPatchRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    data = payload.model_dump(exclude_none=True)
    if payload.points is not None:
        data["points"] = [point.model_dump() for point in payload.points]
    if payload.point is not None:
        data["point"] = payload.point.model_dump()
    return floors_service.patch_geometry(project_id, floor_id, room_id, data, current_user.get("id"))


@router.post("/floors/{floor_id}/rooms/{room_id}/split-by-line")
def split_by_line_alias(
    project_id: str, floor_id: str, room_id: str, payload: RoomSplitLineRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.split_with_line(
        project_id, floor_id, room_id, [point.model_dump() for point in payload.points], current_user.get("id")
    )


@router.post("/floors/{floor_id}/rooms/{room_id}/cutouts")
def create_cutout(
    project_id: str,
    floor_id: str,
    room_id: str,
    payload: RoomCutoutCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.create_cutout(
        project_id,
        floor_id,
        room_id,
        {"points": [point.model_dump() for point in payload.points], "name": payload.name},
        current_user.get("id"),
    )


@router.delete("/floors/{floor_id}/rooms/{room_id}/cutouts/{cutout_id}")
def delete_cutout(
    project_id: str,
    floor_id: str,
    room_id: str,
    cutout_id: str,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.delete_cutout(project_id, floor_id, room_id, cutout_id, current_user.get("id"))


@router.get("/floors/{floor_id}/rooms/{room_id}/revisions")
def room_revisions(project_id: str, floor_id: str, room_id: str, current_user: dict = Depends(get_current_user)):
    _project(project_id, current_user)
    return floors_service.revisions(project_id, floor_id, room_id)


@router.post("/floors/{floor_id}/rooms/{room_id}/revisions/{revision_id}/restore")
def restore_room_revision(
    project_id: str,
    floor_id: str,
    room_id: str,
    revision_id: str,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.restore_revision(project_id, floor_id, room_id, revision_id, current_user.get("id"))


@router.post("/floors/{floor_id}/suggestions/{suggestion_id}/accept")
def accept_suggestion(
    project_id: str,
    floor_id: str,
    suggestion_id: str,
    payload: RoomSuggestionAcceptRequest,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.accept_suggestion(
        project_id,
        floor_id,
        suggestion_id,
        payload.model_dump(exclude_unset=True),
        current_user.get("id"),
    )


@router.post("/floors/{floor_id}/suggestions/{suggestion_id}/correct-with-walls")
def correct_suggestion_with_walls(
    project_id: str,
    floor_id: str,
    suggestion_id: str,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.correct_suggestion_with_walls(
        project_id, floor_id, suggestion_id, current_user.get("id")
    )


@router.post("/floors/{floor_id}/suggestions/{suggestion_id}/reject")
def reject_suggestion(
    project_id: str,
    floor_id: str,
    suggestion_id: str,
    current_user: dict = Depends(get_current_user),
):
    _project(project_id, current_user)
    return floors_service.reject_suggestion(project_id, floor_id, suggestion_id)
