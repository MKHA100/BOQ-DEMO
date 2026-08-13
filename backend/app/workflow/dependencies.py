from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DependencyJob:
    task_type: str
    floor_id: str | None
    entity_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class DependencyPlanner:
    DIMENSION_PROPERTIES = {"width", "width_mm", "height", "height_mm", "thickness", "thickness_mm"}

    def for_element_property(
        self,
        *,
        floor_id: str,
        element_id: str,
        property_name: str,
        wall_ids: list[str],
    ) -> list[DependencyJob]:
        jobs: list[DependencyJob] = []
        if property_name in self.DIMENSION_PROPERTIES:
            jobs.extend(
                DependencyJob(
                    task_type="walls.recalculate_deduction",
                    floor_id=floor_id,
                    entity_id=wall_id,
                    payload={"wall_id": wall_id, "element_id": element_id},
                )
                for wall_id in wall_ids
            )
        jobs.append(
            DependencyJob(
                task_type="review.refresh",
                floor_id=floor_id,
                entity_id=element_id,
                payload={"entity_type": "element", "entity_id": element_id},
            )
        )
        jobs.append(
            DependencyJob(
                task_type="boq.refresh",
                floor_id=floor_id,
                entity_id=element_id,
                payload={"entity_type": "element", "entity_id": element_id},
            )
        )
        return jobs

    def for_scale_change(self, *, floor_id: str) -> list[DependencyJob]:
        return [
            DependencyJob("measure.elements", floor_id, payload={"floor_id": floor_id}),
            DependencyJob("walls.build_centerlines", floor_id, payload={"floor_id": floor_id}),
            DependencyJob("walls.prepare_quantities", floor_id, payload={"floor_id": floor_id}),
            DependencyJob(
                "rooms.calculate_areas",
                floor_id,
                payload={"floor_id": floor_id, "scale_only": True, "precision_complete": True},
            ),
        ]

    def for_room_geometry(self, *, floor_id: str, room_id: str) -> list[DependencyJob]:
        return [
            DependencyJob(
                "rooms.measure",
                floor_id,
                entity_id=room_id,
                payload={"room_id": room_id},
            ),
        ]

    def for_element_relation(self, *, floor_id: str, element_id: str, target_type: str, target_id: str) -> list[DependencyJob]:
        jobs = [
            DependencyJob(
                "review.refresh",
                floor_id,
                entity_id=element_id,
                payload={"entity_type": "element", "entity_id": element_id},
            ),
            DependencyJob(
                "boq.refresh",
                floor_id,
                entity_id=element_id,
                payload={"entity_type": "element", "entity_id": element_id},
            ),
        ]
        if target_type == "wall":
            jobs.insert(
                0,
                DependencyJob(
                    "walls.recalculate_deduction",
                    floor_id,
                    entity_id=target_id,
                    payload={"wall_id": target_id, "element_id": element_id},
                ),
            )
        return jobs


dependency_planner = DependencyPlanner()
