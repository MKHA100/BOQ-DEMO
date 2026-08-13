from __future__ import annotations


def _cell(x0: float, y0: float, x1: float, y1: float, **extra):
    return {
        "points": [
            {"x": x0, "y": y0}, {"x": x1, "y": y0},
            {"x": x1, "y": y1}, {"x": x0, "y": y1},
        ],
        "wall_ids": ["w1", "w2", "w3", "w4"],
        "opening_ids": [],
        "touches_crop_edge": False,
        **extra,
    }


def _label(text: str, x: float, y: float):
    return {
        "text": text,
        "bbox": {"x0": x - 1, "y0": y - 1, "x1": x + 1, "y1": y + 1},
        "source": "drawing",
        "confidence": 0.95,
    }


def test_missing_toilet_is_recovered_only_from_a_real_wall_cell():
    from app.floors.room_exception_service import room_exception_service

    result = room_exception_service.recover(
        candidates=[],
        wall_cells=[_cell(0, 0, 20, 20)],
        text_blocks=[_label("TOI.", 10, 10)],
    )

    assert result["recovered"] == 1
    room = result["candidates"][0]
    assert room["label_hint"] == "Toilet"
    assert room["space_kind"] == "internal"
    assert room["boundary_source"] == "label_seed_wall_cell"
    assert room["geometry_status"] == "needs_review"


def test_balcony_is_recovered_as_external_and_survives_envelope_filter():
    from shapely.geometry import Polygon
    from app.floors.room_candidate_filter import room_candidate_filter
    from app.floors.room_exception_service import room_exception_service

    recovered = room_exception_service.recover(
        candidates=[],
        wall_cells=[_cell(100, 0, 130, 20)],
        text_blocks=[_label("BAL.", 115, 10)],
    )["candidates"]
    filtered = room_candidate_filter.filter(
        recovered,
        envelope=Polygon([(0, 0), (90, 0), (90, 50), (0, 50)]),
        mm_per_pixel=None,
    )

    assert len(filtered["accepted"]) == 1
    assert filtered["accepted"][0]["label_hint"] == "Balcony"
    assert filtered["accepted"][0]["space_kind"] == "external"


def test_matching_model_room_is_labelled_without_creating_a_duplicate():
    from app.floors.room_exception_service import room_exception_service

    model = _cell(
        1, 1, 21, 21,
        boundary_source="model_seed_wall_region",
        confidence=0.8,
        model_points=[{"x": 1, "y": 1}, {"x": 21, "y": 1}, {"x": 21, "y": 21}],
    )
    result = room_exception_service.recover(
        candidates=[model],
        wall_cells=[_cell(0, 0, 20, 20)],
        text_blocks=[_label("BED ROOM", 10, 10)],
    )

    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["label_hint"] == "Bedroom"
    assert result["candidates"][0]["boundary_source"] == "label_seed_wall_cell"


def test_incompatible_labels_do_not_artificially_split_one_wall_cell():
    from app.floors.room_exception_service import room_exception_service

    result = room_exception_service.recover(
        candidates=[],
        wall_cells=[_cell(0, 0, 100, 60)],
        text_blocks=[_label("BED ROOM", 25, 30), _label("TOI", 75, 30)],
    )

    assert result["recovered"] == 0
    assert result["ambiguous"] == 1
    assert result["candidates"] == []


def test_low_confidence_ocr_label_does_not_create_a_room():
    from app.floors.room_exception_service import room_exception_service

    label = _label("TOI", 10, 10)
    label.update({"source": "drawing_ocr", "confidence": 0.40})
    result = room_exception_service.recover(
        candidates=[],
        wall_cells=[_cell(0, 0, 20, 20)],
        text_blocks=[label],
        minimum_label_confidence=0.72,
    )

    assert result["recovered"] == 0
    assert result["candidates"] == []


def test_compatible_open_plan_labels_share_the_existing_wall_cell():
    from app.floors.room_exception_service import room_exception_service

    result = room_exception_service.recover(
        candidates=[],
        wall_cells=[_cell(0, 0, 100, 60)],
        text_blocks=[_label("DINING", 25, 30), _label("LIVING", 75, 30)],
    )

    assert result["recovered"] == 1
    room = result["candidates"][0]
    assert room["label_hint"] == "Dining Area / Living Room"
    assert room["open_plan"] is True


def test_label_uses_smallest_nested_wall_cell():
    from shapely.geometry import Point
    from app.floors.wall_cell_service import wall_cell_service

    result = wall_cell_service.smallest_containing(
        [_cell(0, 0, 100, 100), _cell(10, 10, 30, 30)],
        Point(20, 20),
    )

    assert result is not None
    assert result[0] == 1
