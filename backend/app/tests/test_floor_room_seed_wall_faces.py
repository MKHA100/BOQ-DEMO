from shapely.geometry import box
from shapely.ops import unary_union

from app.floors.room_seed_service import RoomSeedService


def _points(left: float, top: float, right: float, bottom: float):
    return [
        {"x": left, "y": top},
        {"x": right, "y": top},
        {"x": right, "y": bottom},
        {"x": left, "y": bottom},
    ]


def test_model_room_can_bridge_one_small_missing_wall_when_other_faces_align():
    service = RoomSeedService()
    prepared = {
        "typical_thickness_px": 6.0,
        "wall_footprints": unary_union([
            box(95, 96, 205, 102),
            box(198, 96, 204, 204),
            box(95, 198, 205, 204),
        ]),
        "door_closures": [],
    }
    suggestions = [{
        "id": "seed-1",
        "confidence": 0.9,
        "polygon": {"points": _points(100, 100, 200, 200)},
        "status": "new",
    }]

    candidates = service.candidates(
        suggestions=suggestions,
        prepared=prepared,
        envelope=box(0, 0, 10000, 10000),
    )

    assert len(candidates) == 1
    assert candidates[0]["boundary_source"] == "model_seed_wall_faces"
    assert candidates[0]["wall_alignment"] >= service.minimum_wall_face_support


def test_unsupported_model_outline_remains_provisional():
    service = RoomSeedService()
    prepared = {
        "typical_thickness_px": 6.0,
        "wall_footprints": box(400, 400, 500, 406),
        "door_closures": [],
    }
    suggestions = [{
        "id": "seed-2",
        "confidence": 0.9,
        "polygon": {"points": _points(100, 100, 200, 200)},
        "status": "new",
    }]

    candidates = service.candidates(
        suggestions=suggestions,
        prepared=prepared,
        envelope=box(0, 0, 10000, 10000),
    )

    assert len(candidates) == 1
    assert candidates[0]["boundary_source"] == "model_only"
    assert candidates[0]["wall_alignment"] == 0.0
