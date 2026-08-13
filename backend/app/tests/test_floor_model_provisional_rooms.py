from __future__ import annotations


def _current_crop(project_id: str, floor_id: str) -> None:
    from app.database.session import get_connection
    from app.workflow.repo_base import dumps, now_iso

    now = now_iso()
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO documents(id,project_id,document_type,file_name,mime_type,storage_key,content_hash,size_bytes,status,version,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("model-doc", project_id, "source", "plan.pdf", "application/pdf", "plan.pdf", "hash", 1, "ready", 1, now, now),
        )
        connection.execute(
            "INSERT INTO document_pages(id,project_id,document_id,page_number,width_points,height_points,status,version,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("model-page", project_id, "model-doc", 1, 100, 100, "ready", 1, now, now),
        )
        connection.execute(
            "INSERT INTO floor_crops(id,project_id,floor_id,document_id,document_page_id,coordinates_json,source_width,source_height,crop_version,is_current,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("model-crop", project_id, floor_id, "model-doc", "model-page", dumps({"original_rect": {"x": 0, "y": 0, "width": 100, "height": 100}}), 100, 100, 1, 1, "ready", now, now),
        )
        connection.execute(
            "UPDATE floor_versions SET crop_version=1 WHERE project_id=? AND floor_id=?",
            (project_id, floor_id),
        )


def test_model_result_is_published_as_visible_provisional_room(foundation_db):
    from app.floors.repo import floors_repository
    from app.floors.service import floors_service
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service

    project = project_service.create_project("Provisional room")
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    _current_crop(project["id"], floor["id"])
    run = floors_repository.begin_segmentation_run(
        project_id=project["id"], floor_id=floor["id"], crop_id="model-crop",
        crop_version=1, model_id="room-segmentation-o7iga/4",
    )
    floors_repository.complete_segmentation_run(
        run["id"], raw_response={},
        predictions=[{
            "points": [{"x": 10, "y": 10}, {"x": 90, "y": 10}, {"x": 90, "y": 80}, {"x": 10, "y": 80}],
            "confidence": 0.95,
            "bounding_box": {"x": 50, "y": 45, "width": 80, "height": 70},
        }],
        image_width=100, image_height=100, crop_width=100, crop_height=100,
    )

    result = floors_service.publish_model_results(project["id"], floor["id"])
    assert result["published"] == 1
    room = floors_repository.list_rooms(project["id"], floor["id"])[0]
    assert room["boundary_source"] == "model_only"
    assert room["processing_stage"] == "detected"
    assert room["model_polygon"]["points"]
    assert room["display_polygon"]["points"]
