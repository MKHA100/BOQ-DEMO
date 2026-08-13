from __future__ import annotations

from threading import Event, Thread
from typing import Callable


DETECTION_TASKS = (
    "vision.detect_floor_elements", "vision.detect_rooms", "vision.recover_floor_walls"
)
FAST_TASKS = ("render.floor_crop", "extract.floor_crop_text", "rooms.publish_model_results")
INTERPRETATION_TASKS = ("rooms.interpret_floor", "rooms.interpret_ambiguous")
PRECISION_TASKS = ("rooms.precision_refine", "rooms.calculate_areas")
READ_MODEL_TASKS = ("review.refresh", "boq.refresh")


def start_task_lane_workers(
    *,
    count: int,
    stop_event: Event,
    worker_target: Callable[[str, tuple[str, ...], Event], None],
    worker_id_prefix: str,
    lane_name: str,
    task_types: tuple[str, ...],
) -> list[Thread]:
    threads: list[Thread] = []
    for index in range(max(0, int(count))):
        thread = Thread(
            target=worker_target,
            args=(f"{worker_id_prefix}-{lane_name}-{index + 1}", task_types, stop_event),
            daemon=True,
            name=f"autoboq-{lane_name}-{index + 1}",
        )
        thread.start()
        threads.append(thread)
    return threads


def start_lane_workers(
    *,
    count: int,
    stop_event: Event,
    worker_target: Callable[[str, tuple[str, ...], Event], None],
    worker_id_prefix: str,
    task_types: tuple[str, ...] = DETECTION_TASKS,
) -> list[Thread]:
    return start_task_lane_workers(
        count=count,
        stop_event=stop_event,
        worker_target=worker_target,
        worker_id_prefix=worker_id_prefix,
        lane_name="detection",
        task_types=task_types,
    )
