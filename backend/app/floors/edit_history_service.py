from __future__ import annotations

from app.floors.repo import floors_repository


class EditHistoryService:
    def record(self, project_id: str, floor_id: str, room: dict, action: str, created_by: str | None, metadata: dict | None = None) -> dict:
        return floors_repository.create_geometry_revision(
            project_id=project_id,
            floor_id=floor_id,
            room_id=str(room["id"]),
            geometry=room.get("geometry") or {},
            action=action,
            created_by=created_by,
            metadata=metadata or {},
        )


edit_history_service = EditHistoryService()
