from __future__ import annotations


def _project_with_crops():
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    from app.database.session import get_connection
    from app.workflow.repo_base import now_iso
    from uuid import uuid4

    project = project_service.create_project("Scale Tower")
    floors = [workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None) for _ in range(2)]
    now = now_iso()
    with get_connection() as connection:
        document_id = str(uuid4())
        page_id = str(uuid4())
        connection.execute("INSERT INTO documents (id,project_id,document_type,file_name,mime_type,storage_key,size_bytes,status,version,created_at,updated_at) VALUES (?,?,?,?,?,?,0,'ready',1,?,?)", (document_id,project["id"],"source","plans.pdf","application/pdf","plans.pdf",now,now))
        connection.execute("INSERT INTO document_pages (id,project_id,document_id,page_number,width_points,height_points,status,version,created_at,updated_at) VALUES (?,?,?,?,600,400,'ready',1,?,?)", (page_id,project["id"],document_id,1,now,now))
        for floor in floors:
            connection.execute("UPDATE floor_versions SET crop_version=1 WHERE floor_id=?", (floor["id"],))
            connection.execute("INSERT INTO floor_crops (id,project_id,floor_id,document_id,document_page_id,coordinates_json,source_width,source_height,crop_version,status,is_current,created_at,updated_at,source_page_number,original_page_width,original_page_height,rotation,render_dpi) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (str(uuid4()),project["id"],floor["id"],document_id,page_id,"{}",600,400,1,"ready",1,now,now,1,600,400,0,144))
    return project, floors


def test_multifloor_calibration_isolated_and_normalized(foundation_db):
    from app.scale.service import scale_service
    from app.database.session import get_connection

    project, floors = _project_with_crops()
    result = scale_service.save(project_id=project["id"], floor_id=floors[1]["id"], payload={"point_a":{"x":10,"y":10},"point_b":{"x":110,"y":10},"real_distance":5,"unit":"m","crop_version":1}, confirmed_by=None)
    assert result["calibration"]["real_distance_mm"] == 5000
    assert result["calibration"]["mm_per_pixel"] == 50
    assert {job["floor_id"] for job in result["jobs"]} == {floors[1]["id"]}
    with get_connection() as connection:
        versions = connection.execute("SELECT floor_id,scale_version FROM floor_versions ORDER BY floor_id").fetchall()
    values = {row["floor_id"]: row["scale_version"] for row in versions}
    assert values[floors[0]["id"]] == 0
    assert values[floors[1]["id"]] == 1


def test_verification_can_mark_needs_review(foundation_db):
    from app.scale.service import scale_service

    project, floors = _project_with_crops()
    result = scale_service.save(project_id=project["id"], floor_id=floors[0]["id"], payload={"point_a":{"x":0,"y":0},"point_b":{"x":100,"y":0},"real_distance":1,"unit":"m","crop_version":1,"verification":{"point_a":{"x":0,"y":0},"point_b":{"x":200,"y":0},"expected_distance":1,"unit":"m"}}, confirmed_by=None)
    assert result["calibration"]["status"] == "needs_review"


def test_feet_and_inches_calibration_and_verification(foundation_db):
    from app.scale.service import scale_service

    project, floors = _project_with_crops()
    result = scale_service.save(
        project_id=project["id"],
        floor_id=floors[0]["id"],
        payload={
            "point_a": {"x": 0, "y": 0},
            "point_b": {"x": 100, "y": 0},
            "unit": "ft_in",
            "feet": 14,
            "inches": 5,
            "crop_version": 1,
            "verification": {
                "point_a": {"x": 0, "y": 0},
                "point_b": {"x": 72, "y": 0},
                "unit": "ft_in",
                "feet": 10,
                "inches": 5,
            },
        },
        confirmed_by=None,
    )

    assert result["calibration"]["real_distance_mm"] == 4394.2
    assert result["calibration"]["input_unit"] == "ft_in"
    assert result["calibration"]["verification_expected_mm"] == 3175.0


def test_feet_and_inches_schema_rejects_twelve_inches():
    import pytest
    from pydantic import ValidationError
    from app.scale.schemas import CalibrationSaveRequest

    with pytest.raises(ValidationError):
        CalibrationSaveRequest.model_validate({
            "point_a": {"x": 0, "y": 0},
            "point_b": {"x": 100, "y": 0},
            "unit": "ft_in",
            "feet": 10,
            "inches": 12,
            "crop_version": 1,
        })


def test_scale_uses_immediate_preview_before_high_resolution_crop(foundation_db):
    from app.scale.service import scale_service
    from app.database.session import get_connection
    project, floors = _project_with_crops()
    with get_connection() as connection:
        connection.execute("UPDATE floor_crops SET crop_asset_key=NULL, preview_asset_key='floor-preview.png', status='processing' WHERE floor_id=? AND is_current=1",(floors[0]["id"],))
    state=scale_service.get_state(project)
    floor=next(item for item in state["floors"] if item["id"]==floors[0]["id"])
    assert floor["drawing_url"].endswith("/crop-asset")
