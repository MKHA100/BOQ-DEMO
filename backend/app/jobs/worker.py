from __future__ import annotations

import argparse
import logging
import socket
import sys
import time
import json
from threading import Event, Thread
from collections.abc import Callable, Iterable
from uuid import uuid4

from app.core.config import settings
from app.core.logging import configure_logging
from app.database.session import init_db
from app.jobs.job_models import register_job_type
from app.jobs.job_repository import job_repository
from app.jobs.lane_executor import (
    DETECTION_TASKS,
    FAST_TASKS,
    INTERPRETATION_TASKS,
    PRECISION_TASKS,
    READ_MODEL_TASKS,
    start_lane_workers,
    start_task_lane_workers,
)
from app.workflow.jobs import register_foundation_job_specs

# When this module is started with ``python -m app.jobs.worker``, Python
# initially loads it as ``__main__``. Processor modules import
# ``app.jobs.worker`` to register their handlers. Point that module name at
# this running instance so all handlers share the same PROCESSORS registry.
if __name__ == "__main__":
    sys.modules["app.jobs.worker"] = sys.modules[__name__]

JobProcessor = Callable[[dict], dict]
PROCESSORS: dict[str, JobProcessor] = {}
_PROCESSORS_REGISTERED = False
logger = logging.getLogger("autoboq.worker")


def _register_processors() -> None:
    global _PROCESSORS_REGISTERED
    if _PROCESSORS_REGISTERED and "ingest.page_metadata" in PROCESSORS and "export.generate" in PROCESSORS:
        return

    register_foundation_job_specs()
    from app.pdf_upload.jobs import register_pdf_upload_processors

    register_pdf_upload_processors()
    from app.floor_plans.jobs import register_floor_plan_processors

    register_floor_plan_processors()
    from app.specifications.jobs import register_specification_processors

    register_specification_processors()
    from app.scale.jobs import register_scale_processors

    register_scale_processors()
    from app.model_review.jobs import register_model_review_processors

    register_model_review_processors()
    from app.walls.jobs import register_walls_processors

    register_walls_processors()
    from app.floors.jobs import register_floors_processors

    register_floors_processors()
    from app.review.jobs import register_review_processors

    register_review_processors()
    from app.boq.jobs import register_boq_processors

    register_boq_processors()
    _PROCESSORS_REGISTERED = True


def register_processor(
    task_type: str,
    processor: JobProcessor,
    *,
    category: str | None = None,
    label: str | None = None,
    retry_limit: int = 3,
    floor_scoped: bool = False,
) -> None:
    register_job_type(
        task_type,
        label,
        category=category,
        retry_limit=retry_limit,
        floor_scoped=floor_scoped,
    )
    PROCESSORS[task_type] = processor


def process_one(worker_id: str | None = None, task_types: Iterable[str] | None = None) -> dict | None:
    _register_processors()
    allowed = [item for item in (task_types or PROCESSORS.keys()) if item in PROCESSORS]
    if not allowed:
        return None
    resolved_worker_id = worker_id or _worker_id()
    job = job_repository.claim_next_job(
        worker_id=resolved_worker_id,
        task_types=allowed,
        lease_seconds=settings.worker_lease_seconds,
    )
    if not job:
        return None
    logger.info(
        "Starting job id=%s task=%s project=%s floor=%s attempt=%s/%s",
        job.get("id"),
        job.get("task_type"),
        job.get("project_id"),
        job.get("floor_id") or "all",
        job.get("attempts"),
        job.get("max_attempts"),
    )
    stop_heartbeat = Event()
    heartbeat_thread = Thread(
        target=_heartbeat_loop,
        args=(job["id"], resolved_worker_id, stop_heartbeat),
        daemon=True,
    )
    try:
        job_repository.heartbeat(
            job["id"],
            worker_id=resolved_worker_id,
            lease_seconds=settings.worker_lease_seconds,
        )
        if _is_superseded(job):
            result = {"message": "Superseded", "superseded": True}
        else:
            heartbeat_thread.start()
            result = PROCESSORS[job["task_type"]](job) or {}
        completed = job_repository.complete_job(job["id"], result=result, message=result.get("message") or "Ready")
        _refresh_document_status(job, result)
        logger.info("Completed job id=%s task=%s", job.get("id"), job.get("task_type"))
        return completed
    except Exception as exc:
        failed = job_repository.fail_job(job["id"], error_message=str(exc), retry=True)
        _refresh_document_status(job, {})
        if (job.get("task_type") == "render.floor_crop" and failed and failed.get("status") == "failed"):
            _mark_floor_crop_failed(job)
        logger.exception(
            "Job failed id=%s task=%s next_status=%s",
            job.get("id"),
            job.get("task_type"),
            failed.get("status") if failed else "unknown",
        )
        return failed
    finally:
        stop_heartbeat.set()
        if heartbeat_thread.is_alive():
            heartbeat_thread.join(timeout=1.0)



def _heartbeat_loop(job_id: str, worker_id: str, stopped: Event) -> None:
    interval = max(5.0, float(settings.worker_lease_seconds) / 3.0)
    while not stopped.wait(interval):
        job_repository.heartbeat(
            job_id,
            worker_id=worker_id,
            lease_seconds=settings.worker_lease_seconds,
        )


def _is_superseded(job: dict) -> bool:
    floor_id = job.get("floor_id")
    project_id = job.get("project_id")
    task_type = str(job.get("task_type") or "")
    if not floor_id or not project_id:
        return False
    # Read models and exports intentionally read the latest committed state.
    if task_type.startswith(("review.", "boq.", "export.")):
        return False
    raw = job.get("input_versions_json")
    if isinstance(raw, dict):
        expected = raw
    else:
        try:
            parsed = json.loads(raw or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
        expected = parsed if isinstance(parsed, dict) else {}
    if task_type.startswith("vision."):
        relevant = ("crop_version", "schedule_version")
    elif task_type.startswith("measure."):
        relevant = ("crop_version", "scale_version", "element_version")
    elif task_type == "walls.recalculate_deduction":
        relevant = ("element_version",)
    elif task_type in {"walls.build_lines", "walls.build_centerlines"}:
        # Wall generation deliberately consumes the latest committed element
        # set for the same crop. Tag/OCR work may advance element_version after
        # detection without changing wall geometry, so it must not cancel this
        # automatic handoff.
        relevant = ("crop_version",)
    elif task_type.startswith("walls."):
        relevant = ("crop_version", "scale_version")
    elif task_type.startswith("rooms."):
        relevant = ("crop_version", "scale_version", "wall_version")
    else:
        return False
    comparable = {key: expected.get(key) for key in relevant if expected.get(key) is not None}
    if not comparable:
        return False
    try:
        from app.database.session import get_connection

        with get_connection() as connection:
            current = connection.execute(
                "SELECT * FROM floor_versions WHERE project_id = ? AND floor_id = ?",
                (project_id, floor_id),
            ).fetchone()
        if not current:
            return False
        return any(int(current[key] or 0) > int(value or 0) for key, value in comparable.items() if key in current.keys())
    except Exception:
        return False


def _cleanup_queue() -> None:
    try:
        result = job_repository.cleanup_pending_queue()
        total = int(result.get("coalesced") or 0) + int(result.get("superseded") or 0)
        if total:
            logger.info("Cleaned worker queue coalesced=%s superseded=%s",
                result.get("coalesced",0),result.get("superseded",0))
    except Exception:
        logger.exception("Unable to clean pending worker queue")


def _mark_floor_crop_failed(job: dict) -> None:
    try:
        from app.floor_plans.repo import floor_plans_repository
        payload=job.get("payload_json")
        if not isinstance(payload,dict):payload=json.loads(payload or "{}")
        crop_id=str((payload or {}).get("crop_id") or "")
        if crop_id:floor_plans_repository.mark_crop_failed(crop_id)
    except Exception:
        logger.exception("Unable to mark floor crop failed")


def _schedule_background_floor_analysis() -> None:
    try:
        from app.floors.service import floors_service
        from app.model_review.service import model_review_service

        result = floors_service.enqueue_missing_background_analyses()
        count = int(result.get("floors") or 0)
        if count:
            logger.info("Queued background room analysis for %s floor(s)", count)
        wall_result = model_review_service.enqueue_missing_wall_recoveries()
        wall_count = int(wall_result.get("floors") or 0)
        if wall_count:
            logger.info("Queued automatic wall recovery for %s floor(s)", wall_count)
    except Exception:
        # A repair/backfill failure must never prevent the worker from starting.
        logger.exception("Unable to schedule background room analysis")


def _lane_loop(worker_id: str, task_types: tuple[str, ...], stop_event: Event) -> None:
    interval = max(0.5, float(settings.worker_poll_interval_seconds))
    while not stop_event.is_set():
        if not process_one(worker_id, task_types):
            stop_event.wait(interval)


def run_forever(
    worker_id: str | None = None,
    poll_interval_seconds: float | None = None,
    task_types: Iterable[str] | None = None,
) -> None:
    init_db()
    _register_processors()
    _cleanup_queue()
    _schedule_background_floor_analysis()
    resolved_worker_id = worker_id or _worker_id()
    interval = poll_interval_seconds or settings.worker_poll_interval_seconds
    requested = tuple(task_types or PROCESSORS.keys())
    detection_allowed = tuple(item for item in DETECTION_TASKS if item in requested and item in PROCESSORS)
    fast_allowed = tuple(item for item in FAST_TASKS if item in requested and item in PROCESSORS)
    interpretation_allowed = tuple(item for item in INTERPRETATION_TASKS if item in requested and item in PROCESSORS)
    precision_allowed = tuple(item for item in PRECISION_TASKS if item in requested and item in PROCESSORS)
    read_model_allowed = tuple(item for item in READ_MODEL_TASKS if item in requested and item in PROCESSORS)
    lane_task_set = set(detection_allowed + fast_allowed + interpretation_allowed + precision_allowed + read_model_allowed)
    main_allowed = tuple(item for item in requested if item in PROCESSORS and item not in lane_task_set)
    stop_event = Event()
    lane_threads = start_lane_workers(
        count=settings.model_detection_max_concurrency if detection_allowed else 0,
        stop_event=stop_event,
        worker_target=_lane_loop,
        worker_id_prefix=resolved_worker_id,
        task_types=detection_allowed,
    )
    for lane_name, allowed, count in (
        ("fast", fast_allowed, 1),
        ("interpretation", interpretation_allowed, 1),
        ("precision", precision_allowed, settings.room_precision_max_concurrency),
        ("read-model", read_model_allowed, 1),
    ):
        if allowed:
            lane_threads.extend(
                start_task_lane_workers(
                    count=count,
                    stop_event=stop_event,
                    worker_target=_lane_loop,
                    worker_id_prefix=resolved_worker_id,
                    lane_name=lane_name,
                    task_types=allowed,
                )
            )
    logger.info(
        "AutoBOQ worker started id=%s main_tasks=%s detection_workers=%s poll_interval=%ss",
        resolved_worker_id,
        ",".join(main_allowed),
        len(lane_threads),
        interval,
    )
    try:
        while True:
            if not main_allowed or not process_one(resolved_worker_id, main_allowed):
                time.sleep(max(0.5, float(interval)))
    except KeyboardInterrupt:
        logger.info("Stopping AutoBOQ worker id=%s", resolved_worker_id)
    finally:
        stop_event.set()
        for thread in lane_threads:
            thread.join(timeout=2.0)



def drain_pending_jobs(
    worker_id: str | None = None,
    task_types: Iterable[str] | None = None,
) -> int:
    """Process all currently pending jobs, then exit.

    This is useful for local development when the user wants to clear the
    current queue without keeping a long-running worker terminal open.
    """
    init_db()
    _register_processors()
    _cleanup_queue()
    _schedule_background_floor_analysis()
    resolved_worker_id = worker_id or _worker_id()
    processed = 0
    while process_one(resolved_worker_id, task_types):
        processed += 1
    logger.info("AutoBOQ worker drain complete processed=%s", processed)
    return processed

def _refresh_document_status(job: dict, result: dict) -> None:
    try:
        import json
        from app.pdf_upload.service import pdf_upload_service

        payload = job.get("payload_json")
        if not isinstance(payload, dict):
            payload = json.loads(payload or "{}")
        document_id = result.get("document_id") or payload.get("document_id")
        project_id = job.get("project_id") or payload.get("project_id")
        if document_id and project_id:
            pdf_upload_service.refresh_ingestion_status(str(project_id), str(document_id))
    except Exception:
        return


def _worker_id() -> str:
    return f"{socket.gethostname()}-{uuid4().hex[:8]}"


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Run AutoBOQ background jobs")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Process one queued job and exit")
    mode.add_argument("--drain", action="store_true", help="Process all currently queued jobs and exit")
    parser.add_argument("--worker-id", default=None)
    parser.add_argument("--tasks", default="", help="Comma-separated task types")
    args = parser.parse_args()
    init_db()
    _register_processors()
    tasks = [item.strip() for item in args.tasks.split(",") if item.strip()] or None
    if args.once:
        process_one(args.worker_id, tasks)
    elif args.drain:
        drain_pending_jobs(args.worker_id, tasks)
    else:
        run_forever(args.worker_id, task_types=tasks)


if __name__ == "__main__":
    main()
