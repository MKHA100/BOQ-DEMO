from __future__ import annotations


def test_room_detection_is_claimed_before_shared_element_detection(foundation_db):
    from app.jobs.job_repository import job_repository
    from app.projects.project_service import project_service

    project = project_service.create_project("Room priority")
    common = dict(
        category="vision",
        project_id=project["id"],
        floor_id=None,
        payload={},
        input_versions={"crop_version": 1},
        created_by=None,
        max_attempts=1,
    )
    job_repository.create_or_get_job(
        task_type="vision.detect_floor_elements", job_key="elements-priority", **common
    )
    job_repository.create_or_get_job(
        task_type="vision.detect_rooms", job_key="rooms-priority", **common
    )

    claimed = job_repository.claim_next_job(
        worker_id="priority-test", task_types={"vision.detect_rooms", "vision.detect_floor_elements"}
    )
    assert claimed is not None
    assert claimed["task_type"] == "vision.detect_rooms"
