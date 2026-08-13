from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_current_user
from app.core.errors import not_found
from app.jobs.job_service import job_service
from app.projects.project_service import project_service

router = APIRouter(tags=["jobs"])


@router.get("/projects/{project_id}/jobs")
def list_project_jobs(
    project_id: str,
    floor_id: str | None = None,
    active_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    project_service.get_project(project_id, current_user.get("id"))
    return {
        "jobs": job_service.list_project_jobs(
            project_id=project_id,
            floor_id=floor_id,
            active_only=active_only,
            limit=limit,
        )
    }


@router.get("/jobs/{job_id}")
def get_job(job_id: str, current_user: dict = Depends(get_current_user)):
    job = job_service.get_job(job_id)
    if not job:
        raise not_found("Job not found.")
    if job.get("project_id"):
        project_service.get_project(job["project_id"], current_user.get("id"))
    return job
