from __future__ import annotations

import math
from typing import Iterable, Literal

Point = dict[str, float]
Centerline = dict[str, Point]


def as_point(value: dict | None) -> Point | None:
    """Return a finite, normalized point or ``None`` for invalid input."""
    if not isinstance(value, dict):
        return None
    try:
        x = float(value["x"])
        y = float(value["y"])
    except (KeyError, TypeError, ValueError):
        return None
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    return {"x": x, "y": y}


def normalize_line(line: dict | None, *, minimum_length: float = 1e-6) -> Centerline | None:
    """Normalize an API centerline and reject missing/non-finite/zero lines."""
    if not isinstance(line, dict):
        return None
    start = as_point(line.get("start"))
    end = as_point(line.get("end"))
    if start is None or end is None:
        return None
    if point_distance(start, end) < minimum_length:
        return None
    return {"start": start, "end": end}


def point_distance(first: dict, second: dict) -> float:
    return math.dist(
        (float(first["x"]), float(first["y"])),
        (float(second["x"]), float(second["y"])),
    )


def line_length(line: dict) -> float:
    normalized = normalize_line(line)
    return point_distance(normalized["start"], normalized["end"]) if normalized else 0.0


def line_midpoint(line: dict) -> Point:
    normalized = normalize_line(line)
    if normalized is None:
        return {"x": 0.0, "y": 0.0}
    return {
        "x": (normalized["start"]["x"] + normalized["end"]["x"]) / 2.0,
        "y": (normalized["start"]["y"] + normalized["end"]["y"]) / 2.0,
    }


def point_line_projection(point: dict, line: dict, *, clamp: bool = True) -> tuple[Point, float]:
    """Project a point onto a line and return ``(projected_point, parameter)``.

    The parameter is zero at ``start`` and one at ``end``. When ``clamp`` is
    true it is limited to the finite segment.
    """
    normalized = normalize_line(line)
    target = as_point(point)
    if normalized is None or target is None:
        return ({"x": 0.0, "y": 0.0}, 0.0)
    x, y = target["x"], target["y"]
    x1, y1 = normalized["start"]["x"], normalized["start"]["y"]
    x2, y2 = normalized["end"]["x"], normalized["end"]["y"]
    dx, dy = x2 - x1, y2 - y1
    denominator = dx * dx + dy * dy
    if denominator <= 1e-12:
        return (dict(normalized["start"]), 0.0)
    parameter = ((x - x1) * dx + (y - y1) * dy) / denominator
    if clamp:
        parameter = max(0.0, min(1.0, parameter))
    return ({"x": x1 + parameter * dx, "y": y1 + parameter * dy}, parameter)


def point_line_distance(point: dict, line: dict) -> float:
    target = as_point(point)
    normalized = normalize_line(line)
    if target is None or normalized is None:
        return math.inf
    projected, _ = point_line_projection(target, normalized)
    return point_distance(target, projected)


def line_angle_degrees(line: dict) -> float:
    """Return the undirected centerline angle in the range ``[0, 180)``."""
    normalized = normalize_line(line)
    if normalized is None:
        return 0.0
    dx = normalized["end"]["x"] - normalized["start"]["x"]
    dy = normalized["end"]["y"] - normalized["start"]["y"]
    return math.degrees(math.atan2(dy, dx)) % 180.0


def angle_difference_degrees(first: dict, second: dict) -> float:
    difference = abs(line_angle_degrees(first) - line_angle_degrees(second)) % 180.0
    return min(difference, 180.0 - difference)


def line_orientation(line: dict, *, tolerance_degrees: float = 6.0) -> Literal["horizontal", "vertical", "angled"]:
    angle = line_angle_degrees(line)
    if min(angle, 180.0 - angle) <= tolerance_degrees:
        return "horizontal"
    if abs(angle - 90.0) <= tolerance_degrees:
        return "vertical"
    return "angled"


def straighten_line(line: dict, *, tolerance_degrees: float = 6.0) -> Centerline:
    """Make near-orthogonal lines exact while retaining their midpoint/extent."""
    normalized = normalize_line(line)
    if normalized is None:
        return {"start": {"x": 0.0, "y": 0.0}, "end": {"x": 0.0, "y": 0.0}}
    orientation = line_orientation(normalized, tolerance_degrees=tolerance_degrees)
    start, end = dict(normalized["start"]), dict(normalized["end"])
    if orientation == "horizontal":
        ordinate = (start["y"] + end["y"]) / 2.0
        start["y"] = ordinate
        end["y"] = ordinate
    elif orientation == "vertical":
        abscissa = (start["x"] + end["x"]) / 2.0
        start["x"] = abscissa
        end["x"] = abscissa
    return {"start": start, "end": end}


def infinite_line_intersection(first: dict, second: dict, *, epsilon: float = 1e-9) -> tuple[Point, float, float] | None:
    """Return intersection and parameters for two infinite lines.

    The result is ``(point, first_parameter, second_parameter)``. Parallel and
    invalid lines return ``None``.
    """
    one = normalize_line(first)
    two = normalize_line(second)
    if one is None or two is None:
        return None
    px, py = one["start"]["x"], one["start"]["y"]
    rx = one["end"]["x"] - px
    ry = one["end"]["y"] - py
    qx, qy = two["start"]["x"], two["start"]["y"]
    sx = two["end"]["x"] - qx
    sy = two["end"]["y"] - qy
    cross = rx * sy - ry * sx
    if abs(cross) <= epsilon:
        return None
    qpx, qpy = qx - px, qy - py
    first_parameter = (qpx * sy - qpy * sx) / cross
    second_parameter = (qpx * ry - qpy * rx) / cross
    return (
        {"x": px + first_parameter * rx, "y": py + first_parameter * ry},
        first_parameter,
        second_parameter,
    )


def segment_intersection(first: dict, second: dict, *, tolerance: float = 1e-6) -> tuple[Point, float, float] | None:
    intersection = infinite_line_intersection(first, second)
    if intersection is None:
        return None
    point, first_parameter, second_parameter = intersection
    first_margin = tolerance / max(line_length(first), tolerance)
    second_margin = tolerance / max(line_length(second), tolerance)
    if not (-first_margin <= first_parameter <= 1.0 + first_margin):
        return None
    if not (-second_margin <= second_parameter <= 1.0 + second_margin):
        return None
    return point, first_parameter, second_parameter


def endpoints(line: dict) -> tuple[Point, Point]:
    normalized = normalize_line(line)
    if normalized is None:
        return ({"x": 0.0, "y": 0.0}, {"x": 0.0, "y": 0.0})
    return dict(normalized["start"]), dict(normalized["end"])


def endpoint_distance(first: dict, second: dict) -> float:
    first_points = endpoints(first)
    second_points = endpoints(second)
    return min(point_distance(one, two) for one in first_points for two in second_points)


def parallel_distance(first: dict, second: dict) -> float:
    """Symmetric perpendicular offset between two near-parallel lines."""
    first_start, first_end = endpoints(first)
    second_start, second_end = endpoints(second)
    first_distances = [
        point_distance(point, point_line_projection(point, second, clamp=False)[0])
        for point in (first_start, first_end)
    ]
    second_distances = [
        point_distance(point, point_line_projection(point, first, clamp=False)[0])
        for point in (second_start, second_end)
    ]
    return min(max(first_distances), max(second_distances))


def projection_interval(line: dict, *, origin: dict, direction: tuple[float, float]) -> tuple[float, float]:
    normalized = normalize_line(line)
    if normalized is None:
        return 0.0, 0.0
    ox, oy = float(origin["x"]), float(origin["y"])
    dx, dy = direction
    values = [
        (normalized[key]["x"] - ox) * dx + (normalized[key]["y"] - oy) * dy
        for key in ("start", "end")
    ]
    return min(values), max(values)


def collinear_overlap(first: dict, second: dict) -> tuple[float, float]:
    """Return ``(overlap, gap)`` measured along the first line direction."""
    normalized = normalize_line(first)
    if normalized is None:
        return 0.0, math.inf
    length = line_length(normalized)
    direction = (
        (normalized["end"]["x"] - normalized["start"]["x"]) / length,
        (normalized["end"]["y"] - normalized["start"]["y"]) / length,
    )
    first_interval = projection_interval(normalized, origin=normalized["start"], direction=direction)
    second_interval = projection_interval(second, origin=normalized["start"], direction=direction)
    overlap = max(0.0, min(first_interval[1], second_interval[1]) - max(first_interval[0], second_interval[0]))
    gap = max(0.0, max(first_interval[0], second_interval[0]) - min(first_interval[1], second_interval[1]))
    return overlap, gap


def merged_collinear_line(first: dict, second: dict) -> Centerline:
    """Create a line spanning both near-collinear inputs on the first axis."""
    normalized = normalize_line(first)
    other = normalize_line(second)
    if normalized is None:
        return other or {"start": {"x": 0.0, "y": 0.0}, "end": {"x": 0.0, "y": 0.0}}
    if other is None:
        return normalized
    length = line_length(normalized)
    direction = (
        (normalized["end"]["x"] - normalized["start"]["x"]) / length,
        (normalized["end"]["y"] - normalized["start"]["y"]) / length,
    )
    all_points = [normalized["start"], normalized["end"], other["start"], other["end"]]
    projected = [
        ((point["x"] - normalized["start"]["x"]) * direction[0] + (point["y"] - normalized["start"]["y"]) * direction[1], point)
        for point in all_points
    ]
    minimum = min(projected, key=lambda item: item[0])[0]
    maximum = max(projected, key=lambda item: item[0])[0]
    # Average the perpendicular offset so tiny detector jitter is not retained.
    normal = (-direction[1], direction[0])
    offset = sum(
        (point["x"] - normalized["start"]["x"]) * normal[0]
        + (point["y"] - normalized["start"]["y"]) * normal[1]
        for point in all_points
    ) / len(all_points)
    origin = {
        "x": normalized["start"]["x"] + normal[0] * offset,
        "y": normalized["start"]["y"] + normal[1] * offset,
    }
    return {
        "start": {"x": origin["x"] + direction[0] * minimum, "y": origin["y"] + direction[1] * minimum},
        "end": {"x": origin["x"] + direction[0] * maximum, "y": origin["y"] + direction[1] * maximum},
    }


def bbox_center(geometry: dict) -> Point:
    return {
        "x": float(geometry.get("x") or 0) + float(geometry.get("width") or 0) / 2,
        "y": float(geometry.get("y") or 0) + float(geometry.get("height") or 0) / 2,
    }


def bbox_centerline(geometry: dict) -> Centerline:
    x = float(geometry.get("x") or 0)
    y = float(geometry.get("y") or 0)
    width = float(geometry.get("width") or 0)
    height = float(geometry.get("height") or 0)
    if width >= height:
        return {"start": {"x": x, "y": y + height / 2}, "end": {"x": x + width, "y": y + height / 2}}
    return {"start": {"x": x + width / 2, "y": y}, "end": {"x": x + width / 2, "y": y + height}}


def farthest_line(lines: Iterable[dict]) -> Centerline:
    points = [point for line in lines for point in endpoints(line)]
    if not points:
        return {"start": {"x": 0.0, "y": 0.0}, "end": {"x": 0.0, "y": 0.0}}
    best = (points[0], points[-1])
    best_distance = -1.0
    for first in points:
        for second in points:
            current = point_distance(first, second)
            if current > best_distance:
                best = (first, second)
                best_distance = current
    return {"start": dict(best[0]), "end": dict(best[1])}
