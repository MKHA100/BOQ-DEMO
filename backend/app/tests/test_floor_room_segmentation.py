from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


def test_room_segmentation_parses_instance_polygons(monkeypatch, tmp_path):
    from app.floors import room_segmentation_provider as module

    image = tmp_path / "floor.png"
    image.write_bytes(b"not-used-by-mocked-provider")

    monkeypatch.setattr(
        module,
        "settings",
        SimpleNamespace(
            roboflow_floor_enabled=True,
            roboflow_api_key="test-key",
            roboflow_api_base_url="https://serverless.roboflow.com",
            roboflow_floor_model_id="room-segmentation-o7iga/4",
            roboflow_floor_confidence=0.45,
            roboflow_floor_timeout_seconds=90,
        ),
    )
    monkeypatch.setattr(module.RoomSegmentationProvider, "_image_size", staticmethod(lambda _path: (1000, 800)))

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "image": {"width": 1000, "height": 800},
                "predictions": [
                    {
                        "class": "room",
                        "confidence": 0.96,
                        "x": 50,
                        "y": 50,
                        "width": 80,
                        "height": 60,
                        "points": [
                            {"x": 10, "y": 20},
                            {"x": 90, "y": 20},
                            {"x": 90, "y": 80},
                            {"x": 10, "y": 80},
                        ],
                    },
                    {
                        "class": "room",
                        "confidence": 0.20,
                        "points": [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}],
                    },
                ],
            }

    monkeypatch.setattr(module.httpx, "post", lambda *args, **kwargs: Response())
    result = module.RoomSegmentationProvider().detect(Path(image))

    assert result["status"] == "ready"
    assert result["model_id"] == "room-segmentation-o7iga/4"
    assert len(result["predictions"]) == 1
    assert len(result["predictions"][0]["points"]) == 4


def test_segmentation_run_cache_is_unique_per_crop_version(foundation_db):
    from app.floors.repo import floors_repository
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    from app.database.session import get_connection
    from app.workflow.repo_base import dumps, now_iso

    project = project_service.create_project("Room Cache")
    floor = workflow_service.create_floor(
        project_id=project["id"], name=None, level_index=None, created_by=None
    )
    now = now_iso()
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO documents(id,project_id,document_type,file_name,mime_type,storage_key,content_hash,size_bytes,status,version,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("doc-cache", project["id"], "source", "x.pdf", "application/pdf", "x.pdf", "x", 1, "ready", 1, now, now),
        )
        connection.execute(
            "INSERT INTO document_pages(id,project_id,document_id,page_number,width_points,height_points,status,version,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("page-cache", project["id"], "doc-cache", 1, 100, 80, "ready", 1, now, now),
        )
        connection.execute(
            "INSERT INTO floor_crops(id,project_id,floor_id,document_id,document_page_id,coordinates_json,source_width,source_height,crop_version,is_current,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("crop-cache", project["id"], floor["id"], "doc-cache", "page-cache", dumps({"original_rect": {"x": 0, "y": 0, "width": 100, "height": 80}}), 100, 80, 1, 1, "ready", now, now),
        )

    first = floors_repository.begin_segmentation_run(
        project_id=project["id"], floor_id=floor["id"], crop_id="crop-cache",
        crop_version=1, model_id="room-segmentation-o7iga/4",
    )
    second = floors_repository.begin_segmentation_run(
        project_id=project["id"], floor_id=floor["id"], crop_id="crop-cache",
        crop_version=1, model_id="room-segmentation-o7iga/4",
    )
    assert first["id"] == second["id"]
