from __future__ import annotations

import math
from collections import defaultdict

Point = dict[str, float]


def _key(point: Point, tolerance: float) -> tuple[int, int]:
    return (round(float(point["x"]) / tolerance), round(float(point["y"]) / tolerance))


def polygon_area(points: list[Point]) -> float:
    if len(points) < 3:
        return 0.0
    return abs(sum(points[i]["x"] * points[(i + 1) % len(points)]["y"] - points[(i + 1) % len(points)]["x"] * points[i]["y"] for i in range(len(points)))) / 2


def polygon_perimeter(points: list[Point]) -> float:
    return sum(math.dist((points[i]["x"], points[i]["y"]), (points[(i + 1) % len(points)]["x"], points[(i + 1) % len(points)]["y"])) for i in range(len(points)))


def self_intersects(points: list[Point]) -> bool:
    def orient(a: Point, b: Point, c: Point) -> float:
        return (b["x"] - a["x"]) * (c["y"] - a["y"]) - (b["y"] - a["y"]) * (c["x"] - a["x"])
    def intersects(a: Point, b: Point, c: Point, d: Point) -> bool:
        return orient(a, b, c) * orient(a, b, d) < 0 and orient(c, d, a) * orient(c, d, b) < 0
    total = len(points)
    for i in range(total):
        for j in range(i + 1, total):
            if i == j or (i + 1) % total == j or i == (j + 1) % total:
                continue
            if intersects(points[i], points[(i + 1) % total], points[j], points[(j + 1) % total]):
                return True
    return False


def polygonize(lines: list[dict], tolerance: float = 4.0) -> list[dict]:
    """Build simple closed cycles from snapped wall centerlines."""
    nodes: dict[tuple[int, int], Point] = {}
    graph: dict[tuple[int, int], set[tuple[int, int]]] = defaultdict(set)
    edge_wall: dict[frozenset, str] = {}
    for item in lines:
        line = item.get("centerline") or {}
        if not line.get("start") or not line.get("end"):
            continue
        a, b = _key(line["start"], tolerance), _key(line["end"], tolerance)
        if a == b:
            continue
        nodes.setdefault(a, {"x": float(line["start"]["x"]), "y": float(line["start"]["y"])})
        nodes.setdefault(b, {"x": float(line["end"]["x"]), "y": float(line["end"]["y"])})
        graph[a].add(b); graph[b].add(a); edge_wall[frozenset((a, b))] = item["id"]
    cycles: dict[tuple[tuple[int, int], ...], dict] = {}
    max_depth = min(max(len(nodes), 4), 40)
    for start in nodes:
        stack: list[tuple[tuple[int, int], list[tuple[int, int]]]] = [(start, [start])]
        while stack:
            current, path = stack.pop()
            if len(path) > max_depth:
                continue
            for nxt in graph[current]:
                if nxt == start and len(path) >= 4:
                    cycle = path[:]
                    variants = []
                    for ordered in (cycle, list(reversed(cycle))):
                        smallest = min(range(len(ordered)), key=lambda index: ordered[index])
                        variants.append(tuple(ordered[smallest:] + ordered[:smallest]))
                    canonical = min(variants)
                    points = [nodes[key] for key in canonical]
                    area = polygon_area(points)
                    if area > tolerance * tolerance * 4:
                        wall_ids = [edge_wall.get(frozenset((canonical[i], canonical[(i + 1) % len(canonical)]))) for i in range(len(canonical))]
                        cycles[canonical] = {"points": points, "wall_ids": [item for item in wall_ids if item]}
                    continue
                if nxt in path or len(path) >= max_depth:
                    continue
                stack.append((nxt, path + [nxt]))
    candidates = sorted(cycles.values(), key=lambda item: polygon_area(item["points"]))
    # Remove large exterior cycles that fully duplicate smaller enclosed areas.
    return candidates[:100]


def point_in_polygon(point: Point, polygon: list[Point]) -> bool:
    inside = False
    j = len(polygon) - 1
    for i, current in enumerate(polygon):
        previous = polygon[j]
        if ((current["y"] > point["y"]) != (previous["y"] > point["y"])) and point["x"] < (previous["x"] - current["x"]) * (point["y"] - current["y"]) / ((previous["y"] - current["y"]) or 1e-9) + current["x"]:
            inside = not inside
        j = i
    return inside
