from __future__ import annotations


def test_single_element_edit_queues_only_one_read_model_pair(foundation_db):
    from app.database.session import get_connection
    from app.model_review.service import model_review_service
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    project=project_service.create_project("Canonical propagation")
    floor=workflow_service.create_floor(project_id=project["id"],name=None,level_index=None,created_by=None)
    element=model_review_service.create(project_id=project["id"],floor_id=floor["id"],payload={"element_type":"door","geometry":{"x":1,"y":1,"width":5,"height":8}},created_by=None)["record"]
    # Clear creation jobs so this assertion covers one later edit.
    with get_connection() as connection:
        connection.execute("DELETE FROM job_runs WHERE project_id=?",(project["id"],))
    model_review_service.update_property(project_id=project["id"],floor_id=floor["id"],element_id=element["id"],property_name="width_mm",value=900,unit="mm",confirm=True,created_by=None)
    # Repeating the same canonical edit must coalesce downstream read models.
    model_review_service.update_property(project_id=project["id"],floor_id=floor["id"],element_id=element["id"],property_name="width_mm",value=910,unit="mm",confirm=True,created_by=None)
    with get_connection() as connection:
        rows=connection.execute("SELECT task_type,COUNT(*) total FROM job_runs WHERE project_id=? AND task_type IN ('review.refresh','boq.refresh') GROUP BY task_type",(project["id"],)).fetchall()
    assert {row["task_type"]:int(row["total"]) for row in rows} == {"review.refresh":1,"boq.refresh":1}
