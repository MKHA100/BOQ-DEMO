from app.jobs.worker import register_processor
from app.review.service import review_service


def refresh(job: dict) -> dict:
    result = review_service.refresh(str(job["project_id"]), str(job["floor_id"]) if job.get("floor_id") else None)
    return {"message": "Review ready", **result}


def register_review_processors() -> None:
    register_processor("review.refresh", refresh, category="review", label="Review refresh", floor_scoped=False)
