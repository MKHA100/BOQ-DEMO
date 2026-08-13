from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

JOB_STATUS_PENDING: Final = "pending"
JOB_STATUS_RUNNING: Final = "running"
JOB_STATUS_COMPLETED: Final = "completed"
JOB_STATUS_FAILED: Final = "failed"
JOB_STATUS_CANCELLED: Final = "cancelled"
ACTIVE_JOB_STATUSES: Final[set[str]] = {JOB_STATUS_PENDING, JOB_STATUS_RUNNING}
FINAL_JOB_STATUSES: Final[set[str]] = {JOB_STATUS_COMPLETED, JOB_STATUS_FAILED, JOB_STATUS_CANCELLED}

JOB_CATEGORIES: Final[set[str]] = {
    "ingest",
    "render",
    "extract",
    "vision",
    "measure",
    "walls",
    "rooms",
    "review",
    "boq",
    "export",
}

JobStatus = Literal["pending", "running", "completed", "failed", "cancelled"]


@dataclass(frozen=True)
class JobTaskSpec:
    task_type: str
    category: str
    label: str
    retry_limit: int = 3
    floor_scoped: bool = False


TASK_SPECS: dict[str, JobTaskSpec] = {}
SUPPORTED_JOB_TYPES: set[str] = set()
JOB_TYPE_LABELS: dict[str, str] = {}


def register_job_type(
    job_type: str,
    label: str | None = None,
    *,
    category: str | None = None,
    retry_limit: int = 3,
    floor_scoped: bool = False,
) -> None:
    clean_type = job_type.strip()
    clean_category = (category or clean_type.split(".", 1)[0]).strip()
    if not clean_type:
        raise ValueError("job_type is required")
    if clean_category not in JOB_CATEGORIES:
        raise ValueError(f"Unsupported job category: {clean_category}")
    clean_label = label or clean_type.replace(".", " ").replace("_", " ").title()
    spec = JobTaskSpec(
        task_type=clean_type,
        category=clean_category,
        label=clean_label,
        retry_limit=max(1, int(retry_limit)),
        floor_scoped=floor_scoped,
    )
    TASK_SPECS[clean_type] = spec
    SUPPORTED_JOB_TYPES.add(clean_type)
    JOB_TYPE_LABELS[clean_type] = clean_label


def get_task_spec(task_type: str) -> JobTaskSpec:
    try:
        return TASK_SPECS[task_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported background job type: {task_type}") from exc
