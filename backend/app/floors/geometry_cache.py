from __future__ import annotations

from app.floors.repo import floors_repository


class PrecisionGeometryCache:
    def get(self, project_id: str, floor_id: str, key: str):
        return floors_repository.get_geometry_cache(project_id, floor_id, key)

    def put(self, *, project_id: str, floor_id: str, crop_version: int, wall_version: int, scale_version: int, key: str, payload: dict):
        return floors_repository.save_geometry_cache(
            project_id=project_id,
            floor_id=floor_id,
            crop_version=crop_version,
            wall_version=wall_version,
            scale_version=scale_version,
            cache_key=key,
            payload=payload,
        )


precision_geometry_cache = PrecisionGeometryCache()
