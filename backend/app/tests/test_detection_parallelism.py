from __future__ import annotations

from threading import Event


def test_detection_lane_starts_configured_workers(foundation_db):
    from app.jobs.lane_executor import start_lane_workers
    stopped = Event(); calls=[]
    def target(worker_id, task_types, stop_event):
        calls.append((worker_id, tuple(task_types))); stop_event.set()
    threads = start_lane_workers(count=2, stop_event=stopped, worker_target=target, worker_id_prefix="test")
    for thread in threads: thread.join(timeout=2)
    assert len(threads) == 2
    assert len(calls) >= 1
    assert all("vision.detect_floor_elements" in task_types for _, task_types in calls)


def test_detection_lane_honors_a_filtered_task_set(foundation_db):
    from app.jobs.lane_executor import start_lane_workers

    stopped = Event()
    calls = []

    def target(worker_id, task_types, stop_event):
        calls.append((worker_id, tuple(task_types)))
        stop_event.set()

    threads = start_lane_workers(
        count=1,
        stop_event=stopped,
        worker_target=target,
        worker_id_prefix="test",
        task_types=("vision.detect_rooms",),
    )
    for thread in threads:
        thread.join(timeout=2)
    assert calls == [("test-detection-1", ("vision.detect_rooms",))]
