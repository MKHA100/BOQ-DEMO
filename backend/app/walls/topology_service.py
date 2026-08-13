from __future__ import annotations

from copy import deepcopy
import math
from statistics import median
from typing import Any

from app.walls.geometry import (
    angle_difference_degrees,
    bbox_centerline,
    collinear_overlap,
    endpoints,
    infinite_line_intersection,
    line_length,
    merged_collinear_line,
    normalize_line,
    parallel_distance,
    point_distance,
    point_line_projection,
    straighten_line,
)
from app.walls.rules import WallTopologyRules, topology_rules


class WallTopologyService:
    """Conservatively clean detected wall centerlines without database access.

    Inputs are ordinary wall dictionaries. A wall may provide ``centerline`` or
    a detector ``geometry`` bbox. Explicitly manual walls are immutable. The
    returned records are copies, so callers can decide how/when to persist them.
    """

    _MANUAL_SOURCES = {"manual", "user", "user_drawn", "manual_override"}

    def clean_network(
        self,
        walls: list[dict[str, Any]],
        *,
        openings: list[dict[str, Any]] | None = None,
        drawing_width: float | None = None,
        drawing_height: float | None = None,
        mm_per_pixel: float | None = None,
        typical_thickness_px: float | None = None,
        rules: WallTopologyRules | dict[str, Any] | None = None,
        preserve_manual: bool = True,
    ) -> dict[str, Any]:
        """Straighten, connect, de-duplicate and merge a wall network.

        ``removed_wall_ids`` identifies records that a persistence layer may
        suppress. ``merged_wall_ids`` maps each removed ID to its survivor.
        Existing inputs are never mutated.
        """
        prepared, invalid = self._prepare(walls, mm_per_pixel=mm_per_pixel)
        thicknesses = [
            float(item.get("detected_thickness_px") or 0)
            for item in prepared
            if float(item.get("detected_thickness_px") or 0) > 0
        ]
        resolved_thickness = typical_thickness_px
        if resolved_thickness is None and thicknesses:
            resolved_thickness = float(median(thicknesses))
        resolved_rules = topology_rules(
            drawing_width=drawing_width,
            drawing_height=drawing_height,
            typical_thickness_px=resolved_thickness,
            overrides=rules,
        )
        opening_items = openings or []

        for item in prepared:
            item["_protected"] = preserve_manual and self._is_manual(item)
            item["_changed"] = bool(item.get("topology_changed"))

        straightened = self._straighten(prepared, resolved_rules)
        snapped = self._snap_endpoints(prepared, opening_items, resolved_rules)
        extended = self._extend_to_intersections(prepared, opening_items, resolved_rules)
        segment_snapped = self._snap_endpoints_to_segments(prepared, opening_items, resolved_rules)
        snapped += self._snap_endpoints(prepared, opening_items, resolved_rules)
        prepared, removed, merged_map, merged_count, duplicate_count = self._merge_network(
            prepared, opening_items, resolved_rules
        )

        output: list[dict[str, Any]] = []
        changed_ids: list[str] = []
        for item in prepared:
            changed = bool(item.pop("_changed", False))
            item.pop("_protected", None)
            item["topology_changed"] = changed
            if changed:
                changed_ids.append(str(item["id"]))
            output.append(item)

        warnings = [
            {
                "code": "invalid_centerline",
                "severity": "error",
                "message": "Wall has no valid centerline or detection box.",
                "wall_ids": [wall_id],
            }
            for wall_id in invalid
        ]
        summary = {
            "input": len(walls),
            "output": len(output),
            "invalid": len(invalid),
            "straightened": straightened,
            "snapped_endpoints": snapped,
            "snapped_to_segments": segment_snapped,
            "extended_endpoints": extended,
            "merged": merged_count,
            "duplicates_removed": duplicate_count,
            "manual_preserved": sum(self._is_manual(item) for item in output),
        }
        return {
            "walls": output,
            "removed_wall_ids": removed,
            "merged_wall_ids": merged_map,
            "changed_wall_ids": changed_ids,
            "warnings": warnings,
            "rules": resolved_rules.as_dict(),
            "stats": summary,
            "summary": summary,
        }

    def clean(
        self,
        walls: list[dict[str, Any]],
        drawing_width: float | None = None,
        drawing_height: float | None = None,
        preserve_manual: bool = True,
        *,
        openings: list[dict[str, Any]] | None = None,
        mm_per_pixel: float | None = None,
        typical_thickness_px: float | None = None,
        rules: WallTopologyRules | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Stable service entry point used by automatic wall jobs."""
        return self.clean_network(
            walls,
            openings=openings,
            drawing_width=drawing_width,
            drawing_height=drawing_height,
            mm_per_pixel=mm_per_pixel,
            typical_thickness_px=typical_thickness_px,
            rules=rules,
            preserve_manual=preserve_manual,
        )

    def process(
        self,
        walls: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Compatibility alias for callers that describe cleanup as processing."""
        return self.clean_network(walls, **kwargs)

    def _prepare(
        self,
        walls: list[dict[str, Any]],
        *,
        mm_per_pixel: float | None,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        prepared: list[dict[str, Any]] = []
        invalid: list[str] = []
        for index, source in enumerate(walls):
            item = deepcopy(source)
            item["id"] = str(item.get("id") or item.get("element_id") or f"wall:{index}")
            line = normalize_line(item.get("centerline"))
            geometry = item.get("geometry") or item.get("detection_geometry") or {}
            if line is None and isinstance(geometry, dict):
                candidate = bbox_centerline(geometry)
                line = normalize_line(candidate)
                try:
                    width = abs(float(geometry.get("width") or 0))
                    height = abs(float(geometry.get("height") or 0))
                    thickness_px = min(width, height)
                except (TypeError, ValueError):
                    thickness_px = 0.0
                if thickness_px > 0:
                    item.setdefault("detected_thickness_px", thickness_px)
                    if not item.get("thickness_mm") and mm_per_pixel and mm_per_pixel > 0:
                        item["thickness_mm"] = thickness_px * float(mm_per_pixel)
            if line is None:
                invalid.append(str(item["id"]))
                continue
            item["centerline"] = line
            prepared.append(item)
        return prepared, invalid

    def _straighten(self, walls: list[dict[str, Any]], rules: WallTopologyRules) -> int:
        changed = 0
        for item in walls:
            if item["_protected"]:
                continue
            previous = item["centerline"]
            updated = straighten_line(previous, tolerance_degrees=rules.straighten_angle_degrees)
            if self._line_changed(previous, updated):
                item["centerline"] = updated
                item["_changed"] = True
                changed += 1
        return changed

    def _snap_endpoints(
        self,
        walls: list[dict[str, Any]],
        openings: list[dict[str, Any]],
        rules: WallTopologyRules,
    ) -> int:
        nodes: list[dict[str, Any]] = []
        for wall_index, item in enumerate(walls):
            for endpoint_name in ("start", "end"):
                nodes.append(
                    {
                        "wall_index": wall_index,
                        "endpoint": endpoint_name,
                        "point": dict(item["centerline"][endpoint_name]),
                        "protected": bool(item["_protected"]),
                    }
                )

        parents = list(range(len(nodes)))

        def find(index: int) -> int:
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        def union(first: int, second: int) -> None:
            one, two = find(first), find(second)
            if one != two:
                parents[two] = one

        for first_index, first in enumerate(nodes):
            for second_index in range(first_index + 1, len(nodes)):
                second = nodes[second_index]
                if first["wall_index"] == second["wall_index"]:
                    continue
                if point_distance(first["point"], second["point"]) > rules.endpoint_snap_px:
                    continue
                if self._bridge_crosses_opening(first["point"], second["point"], openings, rules):
                    continue
                union(first_index, second_index)

        groups: dict[int, list[int]] = {}
        for index in range(len(nodes)):
            groups.setdefault(find(index), []).append(index)

        changed = 0
        for group in groups.values():
            if len(group) < 2:
                continue
            protected = [nodes[index] for index in group if nodes[index]["protected"]]
            generated = [nodes[index] for index in group if not nodes[index]["protected"]]
            if not generated:
                continue
            if protected:
                for node in generated:
                    target = min(protected, key=lambda item: point_distance(node["point"], item["point"]))["point"]
                    changed += self._set_endpoint(walls[node["wall_index"]], node["endpoint"], target)
            else:
                horizontal = []
                vertical = []
                for index in group:
                    node = nodes[index]
                    line = walls[node["wall_index"]]["centerline"]
                    dx = abs(float(line["end"]["x"]) - float(line["start"]["x"]))
                    dy = abs(float(line["end"]["y"]) - float(line["start"]["y"]))
                    if dx > dy * 4:
                        horizontal.append(node)
                    elif dy > dx * 4:
                        vertical.append(node)
                # At an orthogonal corner use the vertical wall's x and the
                # horizontal wall's y. A plain average makes both walls very
                # slightly diagonal again, so repeated auto-fix calls drift.
                target = {
                    "x": (
                        sum(node["point"]["x"] for node in vertical) / len(vertical)
                        if vertical
                        else sum(nodes[index]["point"]["x"] for index in group) / len(group)
                    ),
                    "y": (
                        sum(node["point"]["y"] for node in horizontal) / len(horizontal)
                        if horizontal
                        else sum(nodes[index]["point"]["y"] for index in group) / len(group)
                    ),
                }
                for node in generated:
                    changed += self._set_endpoint(walls[node["wall_index"]], node["endpoint"], target)
        return changed

    def _extend_to_intersections(
        self,
        walls: list[dict[str, Any]],
        openings: list[dict[str, Any]],
        rules: WallTopologyRules,
    ) -> int:
        changed = 0
        # Work against a stable snapshot so loop ordering cannot cascade a line
        # across multiple walls in one cleanup pass.
        reference_lines = [deepcopy(item["centerline"]) for item in walls]
        for index, item in enumerate(walls):
            if item["_protected"]:
                continue
            for endpoint_name, expected_parameter in (("start", 0.0), ("end", 1.0)):
                current = item["centerline"][endpoint_name]
                best: tuple[float, dict[str, float]] | None = None
                for other_index, other in enumerate(reference_lines):
                    if other_index == index:
                        continue
                    current_line = item["centerline"]
                    if angle_difference_degrees(current_line, other) <= rules.parallel_angle_degrees:
                        continue
                    intersection = infinite_line_intersection(current_line, other)
                    if intersection is None:
                        continue
                    point, parameter, other_parameter = intersection
                    distance = point_distance(current, point)
                    if distance > rules.intersection_extension_px:
                        continue
                    first_margin = rules.intersection_extension_px / max(line_length(current_line), 1.0)
                    other_margin = rules.intersection_tolerance_px / max(line_length(other), 1.0)
                    if abs(parameter - expected_parameter) > first_margin:
                        continue
                    if not (-other_margin <= other_parameter <= 1.0 + other_margin):
                        continue
                    if self._bridge_crosses_opening(current, point, openings, rules):
                        continue
                    if best is None or distance < best[0]:
                        best = (distance, point)
                if best is not None and best[0] > 1e-6:
                    changed += self._set_endpoint(item, endpoint_name, best[1])
        return changed

    def _snap_endpoints_to_segments(
        self,
        walls: list[dict[str, Any]],
        openings: list[dict[str, Any]],
        rules: WallTopologyRules,
    ) -> int:
        """Close small T-junction misses by snapping an endpoint to a wall face.

        Detector boxes frequently finish a few pixels before the middle of a
        perpendicular wall. Endpoint clustering cannot repair that case because
        there is no endpoint on the receiving segment. This pass is deliberately
        limited to the normal endpoint snap tolerance and never bridges an
        opening.
        """
        changed = 0
        references = [deepcopy(item["centerline"]) for item in walls]
        for wall_index, item in enumerate(walls):
            if item["_protected"]:
                continue
            for endpoint_name in ("start", "end"):
                point = item["centerline"][endpoint_name]
                best: tuple[float, dict[str, float]] | None = None
                for other_index, other in enumerate(references):
                    if other_index == wall_index:
                        continue
                    if angle_difference_degrees(item["centerline"], other) <= rules.parallel_angle_degrees:
                        continue
                    projected, parameter = point_line_projection(point, other, clamp=True)
                    if not (0.0 <= parameter <= 1.0):
                        continue
                    distance = point_distance(point, projected)
                    if distance <= 1e-6 or distance > rules.endpoint_snap_px:
                        continue
                    if self._bridge_crosses_opening(point, projected, openings, rules):
                        continue
                    if best is None or distance < best[0]:
                        best = (distance, projected)
                if best is not None:
                    changed += self._set_endpoint(item, endpoint_name, best[1])
        return changed

    def _merge_network(
        self,
        walls: list[dict[str, Any]],
        openings: list[dict[str, Any]],
        rules: WallTopologyRules,
    ) -> tuple[list[dict[str, Any]], list[str], dict[str, str], int, int]:
        active = list(walls)
        removed: list[str] = []
        merged_map: dict[str, str] = {}
        merged_count = 0
        duplicate_count = 0
        changed = True
        while changed:
            changed = False
            for first_index, first in enumerate(active):
                for second_index in range(first_index + 1, len(active)):
                    second = active[second_index]
                    if angle_difference_degrees(first["centerline"], second["centerline"]) > rules.parallel_angle_degrees:
                        continue
                    offset = parallel_distance(first["centerline"], second["centerline"])
                    overlap, gap = collinear_overlap(first["centerline"], second["centerline"])
                    first_thickness = float(first.get("detected_thickness_px") or 0)
                    second_thickness = float(second.get("detected_thickness_px") or 0)
                    local_thickness = min(
                        value for value in (first_thickness, second_thickness) if value > 0
                    ) if first_thickness > 0 and second_thickness > 0 else 0.0
                    local_collinear = max(
                        rules.collinear_distance_px,
                        min(8.0, local_thickness * 0.35),
                    )
                    local_gap = max(
                        rules.merge_gap_px,
                        min(22.0, local_thickness * 1.4),
                    )
                    minimum_length = min(line_length(first["centerline"]), line_length(second["centerline"]))
                    overlap_ratio = overlap / max(minimum_length, 1e-9)
                    duplicate = offset <= rules.duplicate_distance_px and overlap_ratio >= rules.duplicate_overlap_ratio

                    if duplicate:
                        if first["_protected"] and second["_protected"]:
                            continue
                        survivor_index, removed_index = self._duplicate_survivor(first_index, second_index, active)
                        survivor = active[survivor_index]
                        duplicate_wall = active[removed_index]
                        if not survivor["_protected"]:
                            survivor["centerline"] = merged_collinear_line(
                                survivor["centerline"], duplicate_wall["centerline"]
                            )
                            survivor["_changed"] = True
                        self._record_merge(survivor, duplicate_wall)
                        removed_id = str(duplicate_wall["id"])
                        removed.append(removed_id)
                        merged_map[removed_id] = str(survivor["id"])
                        active.pop(removed_index)
                        duplicate_count += 1
                        changed = True
                        break

                    if first["_protected"] or second["_protected"]:
                        continue
                    if offset > local_collinear or gap > local_gap:
                        continue
                    if overlap <= 0:
                        closest = self._closest_endpoint_pair(first["centerline"], second["centerline"])
                        if self._bridge_crosses_opening(closest[0], closest[1], openings, rules):
                            continue
                    first["centerline"] = merged_collinear_line(first["centerline"], second["centerline"])
                    first["_changed"] = True
                    self._record_merge(first, second)
                    removed_id = str(second["id"])
                    removed.append(removed_id)
                    merged_map[removed_id] = str(first["id"])
                    active.pop(second_index)
                    merged_count += 1
                    changed = True
                    break
                if changed:
                    break
        return active, removed, merged_map, merged_count, duplicate_count

    @staticmethod
    def _duplicate_survivor(first_index: int, second_index: int, walls: list[dict[str, Any]]) -> tuple[int, int]:
        first, second = walls[first_index], walls[second_index]
        if first["_protected"] and not second["_protected"]:
            return first_index, second_index
        if second["_protected"] and not first["_protected"]:
            return second_index, first_index
        return first_index, second_index

    @staticmethod
    def _record_merge(survivor: dict[str, Any], removed: dict[str, Any]) -> None:
        source_ids = list(survivor.get("merged_source_ids") or [])
        source_ids.extend(removed.get("merged_source_ids") or [])
        source_ids.append(str(removed["id"]))
        survivor["merged_source_ids"] = list(dict.fromkeys(source_ids))

    @staticmethod
    def _closest_endpoint_pair(first: dict, second: dict) -> tuple[dict[str, float], dict[str, float]]:
        pairs = [(one, two) for one in endpoints(first) for two in endpoints(second)]
        return min(pairs, key=lambda pair: point_distance(pair[0], pair[1]))

    def _bridge_crosses_opening(
        self,
        start: dict[str, float],
        end: dict[str, float],
        openings: list[dict[str, Any]],
        rules: WallTopologyRules,
    ) -> bool:
        if point_distance(start, end) <= rules.intersection_tolerance_px:
            return False
        for opening in openings:
            rectangle = self._opening_rectangle(opening, rules.opening_protection_padding_px)
            if rectangle is not None and self._segment_intersects_rectangle(start, end, rectangle):
                return True
        return False

    @staticmethod
    def _opening_rectangle(opening: dict[str, Any], padding: float) -> tuple[float, float, float, float] | None:
        geometry = opening.get("geometry") or opening.get("bbox") or {}
        if not isinstance(geometry, dict):
            return None
        try:
            x = float(geometry.get("x") or 0)
            y = float(geometry.get("y") or 0)
            width = float(geometry.get("width") or 0)
            height = float(geometry.get("height") or 0)
        except (TypeError, ValueError):
            return None
        if width <= 0 or height <= 0:
            points = geometry.get("points") or []
            try:
                xs = [float(point["x"]) for point in points]
                ys = [float(point["y"]) for point in points]
            except (KeyError, TypeError, ValueError):
                return None
            if not xs or not ys:
                return None
            x, y = min(xs), min(ys)
            width, height = max(xs) - x, max(ys) - y
        return x - padding, y - padding, x + width + padding, y + height + padding

    @staticmethod
    def _segment_intersects_rectangle(
        start: dict[str, float],
        end: dict[str, float],
        rectangle: tuple[float, float, float, float],
    ) -> bool:
        """Liang-Barsky segment/axis-aligned-rectangle intersection."""
        min_x, min_y, max_x, max_y = rectangle
        dx = end["x"] - start["x"]
        dy = end["y"] - start["y"]
        p = (-dx, dx, -dy, dy)
        q = (start["x"] - min_x, max_x - start["x"], start["y"] - min_y, max_y - start["y"])
        lower, upper = 0.0, 1.0
        for direction, distance in zip(p, q):
            if abs(direction) <= 1e-12:
                if distance < 0:
                    return False
                continue
            ratio = distance / direction
            if direction < 0:
                lower = max(lower, ratio)
            else:
                upper = min(upper, ratio)
            if lower > upper:
                return False
        return True

    @classmethod
    def _is_manual(cls, wall: dict[str, Any]) -> bool:
        source = str(wall.get("source") or wall.get("geometry_source") or "").lower()
        return bool(
            wall.get("is_manual")
            or wall.get("manually_edited")
            or wall.get("manual_override")
            # Existing canonical wall rows use this flag after an explicit
            # endpoint edit; keeping it protected also makes reruns idempotent
            # after the floor-level Confirm All action.
            or wall.get("user_confirmed")
            or source in cls._MANUAL_SOURCES
        )

    @staticmethod
    def _set_endpoint(item: dict[str, Any], endpoint_name: str, point: dict[str, float]) -> int:
        previous = item["centerline"][endpoint_name]
        if point_distance(previous, point) <= 1e-6:
            return 0
        item["centerline"][endpoint_name] = {"x": float(point["x"]), "y": float(point["y"])}
        item["_changed"] = True
        return 1

    @staticmethod
    def _line_changed(first: dict, second: dict, tolerance: float = 1e-6) -> bool:
        return any(
            point_distance(first[key], second[key]) > tolerance
            for key in ("start", "end")
        )


wall_topology_service = WallTopologyService()
