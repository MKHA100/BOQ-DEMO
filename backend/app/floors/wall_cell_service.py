from __future__ import annotations

from typing import Any

from shapely.geometry import Point, Polygon

from app.floors.polygon_builder import room_polygon_builder
from app.floors.room_semantics import room_semantics


class WallCellService:
    """Build canonical room cells from the confirmed wall network.

    This small boundary keeps wall-derived geometry separate from model
    suggestions.  The model may discover or name a space, but the points used
    for measurement come from a closed wall cell whenever one is available.
    """

    # Keep small bathrooms, stores and WC compartments. Noise is removed by
    # closure/envelope/overlap validation rather than a large area cutoff.
    minimum_room_area_m2 = 0.50

    def build(
        self,
        prepared: dict[str, Any],
        *,
        crop_width: float,
        crop_height: float,
        mm_per_pixel: float | None,
    ) -> list[dict[str, Any]]:
        minimum_area_px = None
        if mm_per_pixel and mm_per_pixel > 0:
            minimum_area_px = self.minimum_room_area_m2 * 1_000_000 / (mm_per_pixel**2)
        cells = room_polygon_builder.build(
            prepared,
            crop_width=crop_width,
            crop_height=crop_height,
            minimum_area_px=minimum_area_px,
        )
        output: list[dict[str, Any]] = []
        for cell in cells:
            polygon = room_polygon_builder.points_to_polygon(cell.get("points") or [])
            if polygon.is_empty:
                continue
            output.append(
                {
                    **cell,
                    "boundary_source": "wall_cell",
                    "measurement_authority": "wall_geometry",
                    "area_px": float(polygon.area),
                    "perimeter_px": float(polygon.length),
                    "geometry_hash": room_polygon_builder.geometry_hash(polygon),
                }
            )
        return output

    @staticmethod
    def attach_relations(candidate: dict[str, Any], cells: list[dict[str, Any]]) -> dict[str, Any]:
        polygon = room_polygon_builder.points_to_polygon(candidate.get("points") or [])
        if polygon.is_empty:
            return candidate
        best: dict[str, Any] | None = None
        best_score = 0.0
        for cell in cells:
            cell_polygon = room_polygon_builder.points_to_polygon(cell.get("points") or [])
            score = room_polygon_builder.iou(polygon, cell_polygon)
            if score > best_score:
                best, best_score = cell, score
        if best is not None and best_score >= 0.20:
            return {
                **candidate,
                "wall_ids": best.get("wall_ids") or [],
                "opening_ids": best.get("opening_ids") or [],
                "wall_cell_score": round(best_score, 6),
            }
        return candidate

    @staticmethod
    def smallest_containing(
        cells: list[dict[str, Any]], point: Point, *, tolerance: float = 1.0
    ) -> tuple[int, Polygon] | None:
        """Return the most specific real wall cell containing a label point."""
        containing: list[tuple[float, int, Polygon]] = []
        for index, cell in enumerate(cells):
            polygon = room_polygon_builder.points_to_polygon(cell.get("points") or [])
            if not polygon.is_empty and polygon.buffer(tolerance).contains(point):
                containing.append((float(polygon.area), index, polygon))
        if not containing:
            return None
        _, index, polygon = min(containing, key=lambda item: item[0])
        return index, polygon

    def split_open_cells(
        self,
        cells: list[dict[str, Any]],
        text_blocks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Partition a wall-connected open plan by printed room labels.

        The labels select the semantic regions, while the resulting polygons
        are still clipped to the canonical wall cell. This handles plans where
        Dining, Sitting and Stair are intentionally connected without walls.
        """
        known = set(room_semantics.NORMALIZATION.values())
        labels: list[dict[str, Any]] = []
        for block in text_blocks:
            bbox = block.get("bbox") or {}
            try:
                center = Point(
                    (float(bbox["x0"]) + float(bbox["x1"])) / 2,
                    (float(bbox["y0"]) + float(bbox["y1"])) / 2,
                )
            except (KeyError, TypeError, ValueError):
                continue
            for label in room_semantics.extract_labels(block.get("text")):
                if label not in known:
                    continue
                # Multiple labels can share one merged PDF text block. They
                # are not independent geometric seeds without distinct points.
                if any(center.distance(item["point"]) < 4.0 for item in labels):
                    continue
                labels.append({"name": label, "point": center})

        output: list[dict[str, Any]] = []
        for cell in cells:
            polygon = room_polygon_builder.points_to_polygon(cell.get("points") or [])
            inside = [item for item in labels if polygon.buffer(1.0).contains(item["point"])]
            if len(inside) < 2:
                output.append(cell)
                continue
            partitions: list[dict[str, Any]] = []
            for label in inside:
                region = polygon
                for other in inside:
                    if other is label:
                        continue
                    region = self._nearest_half_plane(region, label["point"], other["point"])
                    if region.is_empty:
                        break
                region = self._largest_polygon(region)
                if region.is_empty:
                    continue
                partitions.append(
                    {
                        **cell,
                        "points": room_polygon_builder.polygon_to_points(region),
                        "area_px": float(region.area),
                        "perimeter_px": float(region.length),
                        "geometry_hash": room_polygon_builder.geometry_hash(region),
                        "boundary_source": "label_partition",
                        "measurement_authority": "wall_cell_label_partition",
                        "label_hint": label["name"],
                    }
                )
            covered = sum(float(item.get("area_px") or 0) for item in partitions)
            if len(partitions) == len(inside) and covered >= polygon.area * 0.97:
                output.extend(partitions)
            else:
                output.append(cell)
        return output

    @staticmethod
    def _nearest_half_plane(region: Polygon, own: Point, other: Point) -> Polygon:
        nx, ny = other.x - own.x, other.y - own.y
        length = (nx * nx + ny * ny) ** 0.5
        if length < 1e-6:
            return region
        nx, ny = nx / length, ny / length
        dx, dy = -ny, nx
        mx, my = (own.x + other.x) / 2, (own.y + other.y) / 2
        bounds = region.bounds
        span = max(bounds[2] - bounds[0], bounds[3] - bounds[1], length, 1.0) * 8
        half_plane = Polygon(
            [
                (mx + dx * span, my + dy * span),
                (mx - dx * span, my - dy * span),
                (mx - dx * span - nx * span * 2, my - dy * span - ny * span * 2),
                (mx + dx * span - nx * span * 2, my + dy * span - ny * span * 2),
            ]
        )
        return region.intersection(half_plane)

    @staticmethod
    def _largest_polygon(value: Any) -> Polygon:
        return max(
            (item for item in getattr(value, "geoms", [value]) if isinstance(item, Polygon)),
            key=lambda item: item.area,
            default=Polygon(),
        )


wall_cell_service = WallCellService()
