from __future__ import annotations


def test_context_contains_only_selected_floor_and_reduced_image(monkeypatch, tmp_path):
    from PIL import Image
    from app.floors import llm_room_context_service as module

    image = tmp_path / "floor.png"
    Image.new("RGB", (3200, 1600), "white").save(image)
    monkeypatch.setattr(
        module.floors_repository,
        "get_floor_row",
        lambda project_id, floor_id: {
            "id": floor_id,
            "name": "Ground Floor",
            "crop_asset_key": "crop.png",
            "coordinates": {"original_rect": {"width": 800, "height": 400}},
            "crop_version": 3,
            "wall_version": 4,
            "scale_version": 2,
            "mm_per_pixel": 5,
        },
    )
    monkeypatch.setattr(module.storage_service, "key_to_path", lambda _key: image)
    monkeypatch.setattr(module.storage_service, "ensure_local_file", lambda path: path)
    monkeypatch.setattr(module.vector_floor_geometry_service, "extract", lambda *_: {"wall_pairs": [], "dimensions": []})
    monkeypatch.setattr(module.walls_repository, "list_walls", lambda *_: [])
    monkeypatch.setattr(module.walls_repository, "list_opening_elements", lambda *_: [])
    monkeypatch.setattr(
        module.floors_repository,
        "list_suggestions",
        lambda *_: [{"id": "s1", "polygon": {"points": [{"x": 1, "y": 1}, {"x": 20, "y": 1}, {"x": 20, "y": 20}]}, "status": "new"}],
    )
    monkeypatch.setattr(module.floors_repository, "list_rooms", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(module.floors_repository, "list_dimension_observations", lambda *_: [])
    monkeypatch.setattr(module.room_label_service, "blocks", lambda *_: [{"text": "BED ROOM", "bbox": {}}])

    result = module.LLMRoomContextService().build("project-1", "floor-1")
    context = result["context"]
    assert context["project_id"] == "project-1"
    assert context["floor_id"] == "floor-1"
    assert context["coordinate_space"]["width"] == 800
    assert context["coordinate_space"]["submitted_image_width"] == 2400
    assert context["coordinate_space"]["submitted_image_height"] == 1200
    assert context["coordinate_space"]["coordinate_to_submitted_image"] == {
        "scale_x": 3.0,
        "scale_y": 3.0,
    }
    assert context["versions"] == {"crop_version": 3, "wall_version": 4, "scale_version": 2}
    assert context["room_suggestions"][0]["id"] == "s1"
    assert result["image_url"].startswith("data:image/jpeg;base64,")
    assert len(result["input_hash"]) == 64
