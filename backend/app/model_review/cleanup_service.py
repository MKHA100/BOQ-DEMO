from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.database.session import get_connection
from app.jobs.job_service import job_service
from app.model_review.reconciliation_service import intersection_over_union
from app.workflow.repo import workflow_repository
from app.workflow.repo_base import loads, now_iso


class DetectionCleanupService:
    def repair_project(
        self,
        project_id: str,
        floor_id: str | None = None,
        *,
        enqueue_rebuild: bool = True,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        """Supersede obvious generated duplicates without deleting audit history.

        Confirmed rows win over unconfirmed rows. The cleanup increments each
        affected floor only once and can queue one deterministic wall/room/
        Review/BOQ rebuild per affected floor.
        """
        where = ["project_id=?", "COALESCE(is_manual,0)=0", "COALESCE(generated_status,'current')='current'"]
        params: list[Any] = [project_id]
        if floor_id:
            where.append("floor_id=?")
            params.append(floor_id)
        affected_floors: set[str] = set()
        versions_by_floor: dict[str, dict[str, int]] = {}
        with get_connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM elements WHERE {' AND '.join(where)} "
                "ORDER BY user_confirmed DESC, updated_at DESC, created_at DESC",
                tuple(params),
            ).fetchall()
            grouped: dict[tuple[str, str], list[Any]] = defaultdict(list)
            for row in rows:
                grouped[(str(row["floor_id"]), str(row["element_type"]))].append(row)
            superseded: list[str] = []
            kept: list[Any] = []
            for (group_floor_id, _), items in grouped.items():
                group_kept: list[Any] = []
                for row in items:
                    geometry = loads(row["geometry_json"]) or {}
                    duplicate = next(
                        (
                            existing
                            for existing in group_kept
                            if intersection_over_union(loads(existing["geometry_json"]) or {}, geometry) >= 0.82
                        ),
                        None,
                    )
                    if duplicate:
                        superseded.append(str(row["id"]))
                        affected_floors.add(group_floor_id)
                    else:
                        group_kept.append(row)
                kept.extend(group_kept)
            if superseded:
                placeholders = ",".join("?" for _ in superseded)
                connection.execute(
                    f"UPDATE elements SET generated_status='superseded', excluded=1, updated_at=? "
                    f"WHERE id IN ({placeholders})",
                    (now_iso(), *superseded),
                )
                for affected_floor_id in sorted(affected_floors):
                    versions = workflow_repository.increment_floor_version(
                        connection, project_id, affected_floor_id, "element_version"
                    )
                    connection.execute(
                        "UPDATE walls SET is_stale=1,status='not_ready',updated_at=? "
                        "WHERE project_id=? AND floor_id=?",
                        (now_iso(), project_id, affected_floor_id),
                    )
                    connection.execute(
                        "UPDATE boqs SET is_stale=1,status='not_ready',updated_at=? WHERE project_id=?",
                        (now_iso(), project_id),
                    )
                    versions_by_floor[affected_floor_id] = {
                        key: int(versions[key] or 0)
                        for key in versions.keys()
                        if key.endswith("_version")
                    }

        jobs: list[dict[str, Any]] = []
        if enqueue_rebuild:
            for affected_floor_id, versions in versions_by_floor.items():
                job, created = job_service.enqueue(
                    task_type="walls.build_lines",
                    project_id=project_id,
                    floor_id=affected_floor_id,
                    entity_id=affected_floor_id,
                    payload={"floor_id": affected_floor_id, "reason": "duplicate_detection_cleanup"},
                    input_versions=versions,
                    created_by=created_by,
                )
                jobs.append({**job, "created": created})
        return {
            "kept": len(kept),
            "superseded": len(superseded),
            "affected_floors": sorted(affected_floors),
            "jobs": jobs,
        }


detection_cleanup_service = DetectionCleanupService()
