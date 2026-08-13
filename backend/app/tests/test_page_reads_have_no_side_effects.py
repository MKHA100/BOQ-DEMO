from __future__ import annotations


def test_model_review_review_and_boq_gets_do_not_enqueue_jobs(foundation_db):
    from app.boq.service import boq_service
    from app.database.session import get_connection
    from app.model_review.service import model_review_service
    from app.projects.project_service import project_service
    from app.review.service import review_service
    from app.workflow.service import workflow_service
    project=project_service.create_project("Pure reads")
    floor=workflow_service.create_floor(project_id=project["id"],name=None,level_index=None,created_by=None)
    with get_connection() as connection:
        before=connection.execute("SELECT COUNT(*) total FROM job_runs WHERE project_id=?",(project["id"],)).fetchone()["total"]
    model_review_service.get_state(project, floor["id"])
    review_service.state(project)
    boq_service.state(project)
    with get_connection() as connection:
        after=connection.execute("SELECT COUNT(*) total FROM job_runs WHERE project_id=?",(project["id"],)).fetchone()["total"]
    assert after == before
