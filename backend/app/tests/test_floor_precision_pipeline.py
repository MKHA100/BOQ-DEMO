def test_precision_pipeline_regularizes_room(monkeypatch):
    from shapely.geometry import GeometryCollection
    from app.floors.precision_pipeline import precision_room_pipeline
    monkeypatch.setattr("app.floors.precision_pipeline.room_label_service.suggestions", lambda *_: {"r1": {"name": "Kitchen", "room_type": "Kitchen", "label_source": "drawing", "label_candidates": ["Kitchen"], "space_kind": "internal", "include_in_boq": True, "open_plan": False}})
    room = {"id": "r1", "geometry": {"points": [{"x": 0, "y": 0}, {"x": 50, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 80}, {"x": 0, "y": 80}]}, "model_verified": True}
    prepared = {"wall_footprints": GeometryCollection(), "typical_thickness_px": 5, "vector_wall_count": 1}
    floor = {"coordinates": {"original_rect": {"width": 120, "height": 100}}, "mm_per_pixel": 10, "scale_version": 1}
    result = precision_room_pipeline.refine(project_id="p", floor_id="f", floor=floor, rooms=[room], prepared=prepared, evidence={"dimensions": []})
    assert result["r1"]["name"] == "Kitchen"
    assert len(result["r1"]["regularized_geometry"]["points"]) == 4
