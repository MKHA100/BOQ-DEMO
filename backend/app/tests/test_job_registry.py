from app.jobs import job_models
from app.jobs.job_service import job_service
from app.jobs.worker import PROCESSORS, process_one, register_processor
from app.workflow.jobs import register_foundation_job_specs


def setup_function():
    PROCESSORS.clear()
    job_models.TASK_SPECS.clear()
    job_models.SUPPORTED_JOB_TYPES.clear()
    job_models.JOB_TYPE_LABELS.clear()
    register_foundation_job_specs()


def test_worker_is_idle_without_registered_processors(foundation_db):
    assert process_one() is None


def test_job_deduplication_uses_input_versions(foundation_db):
    # Use a real project/floor because the job table enforces scope ownership.
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service

    project = project_service.create_project("Deduplication")
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    first, first_created = job_service.enqueue(
        task_type="measure.floor",
        project_id=project["id"],
        floor_id=floor["id"],
        input_versions={"scale_version": 2},
        entity_id=floor["id"],
    )
    second, second_created = job_service.enqueue(
        task_type="measure.floor",
        project_id=project["id"],
        floor_id=floor["id"],
        input_versions={"scale_version": 2},
        entity_id=floor["id"],
    )
    third, third_created = job_service.enqueue(
        task_type="measure.floor",
        project_id=project["id"],
        floor_id=floor["id"],
        input_versions={"scale_version": 3},
        entity_id=floor["id"],
    )

    assert first_created is True
    assert second_created is False
    assert first["id"] == second["id"]
    assert third_created is True
    assert third["id"] != first["id"]


def test_processor_registration_updates_registry():
    register_processor("measure.test", lambda job: {"message": "Ready"}, category="measure")
    assert "measure.test" in PROCESSORS
    assert "measure.test" in job_models.TASK_SPECS


def test_floor_crop_render_has_priority_over_old_boq(foundation_db):
    from app.jobs.job_service import job_service
    from app.jobs.job_repository import job_repository
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    project = project_service.create_project("Priority")
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    job_service.enqueue(task_type="boq.refresh", project_id=project["id"], payload={"reason":"older"}, input_versions={"boq_version":1})
    render, _ = job_service.enqueue(task_type="render.floor_crop", project_id=project["id"], floor_id=floor["id"], payload={"crop_id":"c1"}, input_versions={"crop_version":1}, entity_id="c1")
    claimed = job_repository.claim_next_job(worker_id="priority-worker", task_types=["boq.refresh","render.floor_crop"], lease_seconds=30)
    assert claimed["id"] == render["id"]

def test_read_model_jobs_are_coalesced(foundation_db):
    from app.jobs.job_service import job_service
    from app.database.session import get_connection
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    project = project_service.create_project("Coalesce")
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    review_ids=[]; boq_ids=[]
    for version in range(1,8):
        review,_=job_service.enqueue(task_type="review.refresh",project_id=project["id"],floor_id=floor["id"],payload={"version":version},input_versions={"review_version":version},entity_id=f"e-{version}")
        boq,_=job_service.enqueue(task_type="boq.refresh",project_id=project["id"],floor_id=floor["id"],payload={"version":version},input_versions={"boq_version":version},entity_id=f"e-{version}")
        review_ids.append(review["id"]); boq_ids.append(boq["id"])
    assert len(set(review_ids)) == 1
    assert len(set(boq_ids)) == 1
    with get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM job_runs WHERE project_id=? AND task_type='review.refresh' AND status='pending'",(project["id"],)).fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM job_runs WHERE project_id=? AND task_type='boq.refresh' AND status='pending'",(project["id"],)).fetchone()[0] == 1
