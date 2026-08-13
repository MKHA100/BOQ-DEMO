from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any

import fitz
from shapely.geometry import LineString, Polygon, box

from app.floor_plans.rendering import crop_clip, crop_source_path
from app.floor_plans.repo import floor_plans_repository
from app.floors.room_semantics import room_semantics


@dataclass(frozen=True)
class Segment:
    start: tuple[float, float]
    end: tuple[float, float]
    width: float

    @property
    def line(self) -> LineString:
        return LineString([self.start, self.end])

    @property
    def length(self) -> float:
        return self.line.length

    @property
    def orientation(self) -> str:
        dx = abs(self.end[0] - self.start[0])
        dy = abs(self.end[1] - self.start[1])
        if dx >= dy * 4:
            return "horizontal"
        if dy >= dx * 4:
            return "vertical"
        return "other"


class VectorFloorGeometryService:
    """Read useful vector lines and printed dimensions from the source PDF.

    Results are only supporting evidence. Model walls remain available when a
    drawing is raster-only or the vector layer is noisy.
    """

    _imperial_dimension = re.compile(
        r"(?<!\d)(\d{1,3})\s*(?:['’′]|FT\.?|FEET)"
        r"(?:\s*[-–]?\s*(\d{1,2}(?:\.\d+)?)\s*(?:[\"”″]|IN\.?|INCH(?:ES)?)?)?",
        re.IGNORECASE,
    )
    _metric_dimension = re.compile(
        r"(?<![\d.])(\d+(?:[.,]\d+)?)\s*(MM|CM|M)(?![A-Z0-9²])",
        re.IGNORECASE,
    )
    _bare_metric_dimension = re.compile(r"(?<!\d)(\d{3,5})(?!\d)")

    def extract(self, project_id: str, floor_id: str) -> dict[str, Any]:
        crop = floor_plans_repository.current_crop(project_id, floor_id)
        if not crop:
            return {"segments": [], "wall_pairs": [], "dimensions": []}
        source_path = crop_source_path(project_id, crop)
        clip = crop_clip(crop)
        page_number = int(crop.get("source_page_number") or 1)
        rotation = int(crop.get("rotation") or 0) % 360
        with fitz.open(source_path) as source:
            page = source.load_page(page_number - 1)
            segments = self._segments(page, clip, rotation)
            blocks = self._text_blocks(page, clip, rotation)
        wall_pairs = self._pair_wall_edges(segments, blocks)
        dimensions = self._dimension_observations(blocks, segments)
        return {
            "segments": [self._serialize_segment(item) for item in segments],
            "wall_pairs": wall_pairs,
            "dimensions": dimensions,
        }

    def _segments(self, page: fitz.Page, clip: fitz.Rect, rotation: int) -> list[Segment]:
        output: list[Segment] = []
        for drawing in page.get_drawings():
            width = float(drawing.get("width") or 0.5)
            for item in drawing.get("items") or []:
                if not item:
                    continue
                code = item[0]
                if code == "l" and len(item) >= 3:
                    points = [item[1], item[2]]
                elif code == "re" and len(item) >= 2:
                    rect = fitz.Rect(item[1])
                    points_list = [
                        (rect.x0, rect.y0, rect.x1, rect.y0),
                        (rect.x1, rect.y0, rect.x1, rect.y1),
                        (rect.x1, rect.y1, rect.x0, rect.y1),
                        (rect.x0, rect.y1, rect.x0, rect.y0),
                    ]
                    for x0, y0, x1, y1 in points_list:
                        mapped = self._map_pair((x0, y0), (x1, y1), clip, rotation)
                        segment = Segment(mapped[0], mapped[1], width)
                        if segment.length >= 8 and segment.orientation != "other":
                            output.append(segment)
                    continue
                else:
                    continue
                try:
                    p0 = (float(points[0].x), float(points[0].y))
                    p1 = (float(points[1].x), float(points[1].y))
                except AttributeError:
                    p0 = (float(points[0][0]), float(points[0][1]))
                    p1 = (float(points[1][0]), float(points[1][1]))
                line = LineString([p0, p1])
                if not line.intersects(box(clip.x0, clip.y0, clip.x1, clip.y1)):
                    continue
                mapped = self._map_pair(p0, p1, clip, rotation)
                segment = Segment(mapped[0], mapped[1], width)
                if segment.length >= 8 and segment.orientation != "other":
                    output.append(segment)
        deduped: dict[tuple[int, int, int, int], Segment] = {}
        for item in output:
            key = tuple(round(value * 2) for value in (*item.start, *item.end))
            reverse = (key[2], key[3], key[0], key[1])
            if reverse in deduped:
                continue
            deduped[key] = item
        return list(deduped.values())[:5000]

    def _text_blocks(self, page: fitz.Page, clip: fitz.Rect, rotation: int) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        for block in page.get_text("blocks", clip=clip, sort=True):
            if len(block) < 7 or int(block[6]) != 0:
                continue
            text = str(block[4] or "").strip()
            if not text:
                continue
            center = ((float(block[0]) + float(block[2])) / 2, (float(block[1]) + float(block[3])) / 2)
            mapped = self._map_point(center, clip, rotation)
            blocks.append({"text": text, "x": mapped[0], "y": mapped[1]})
        return blocks

    def _pair_wall_edges(
        self, segments: list[Segment], blocks: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        annotation_points = [
            (float(block["x"]), float(block["y"]))
            for block in blocks or []
            if self._dimension_values(str(block.get("text") or ""))
            or bool(re.fullmatch(r"\s*(?:SECTION\s*)?[A-Z](?:\s*[-–]\s*[A-Z])?\s*", str(block.get("text") or ""), re.I))
        ]
        candidates = [
            item
            for item in segments
            if item.length >= 25
            and item.orientation in {"horizontal", "vertical"}
            and not (
                item.length < 450
                and any(item.line.distance(fitz_to_shapely_point(point)) < 18 for point in annotation_points)
            )
        ]
        output: list[dict[str, Any]] = []
        used: set[tuple[int, int]] = set()
        for index, first in enumerate(candidates):
            for other_index in range(index + 1, len(candidates)):
                second = candidates[other_index]
                if first.orientation != second.orientation:
                    continue
                separation = self._parallel_distance(first, second)
                if not 2.5 <= separation <= 28:
                    continue
                overlap = self._overlap_ratio(first, second)
                if overlap < 0.72:
                    continue
                score = overlap - abs(separation - 8.0) / 100.0
                key = (index, other_index)
                if key in used:
                    continue
                centerline = self._midline(first, second)
                footprint = centerline.buffer(separation / 2.0, cap_style=2, join_style=2)
                if footprint.is_empty or footprint.area <= 10:
                    continue
                identity = hashlib.sha1(footprint.wkb).hexdigest()[:16]
                output.append({
                    "id": f"vector:{identity}",
                    "centerline": self._line_dict(centerline),
                    "thickness_px": separation,
                    "footprint": self._polygon_points(footprint),
                    "confidence": min(0.98, max(0.55, score)),
                })
                used.add(key)
        # Keep the strongest pairs and remove nearly identical footprints.
        output.sort(key=lambda item: (float(item["confidence"]), LineString([
            (item["centerline"]["start"]["x"], item["centerline"]["start"]["y"]),
            (item["centerline"]["end"]["x"], item["centerline"]["end"]["y"]),
        ]).length), reverse=True)
        selected: list[dict[str, Any]] = []
        polygons: list[Polygon] = []
        for item in output:
            polygon = Polygon([(point["x"], point["y"]) for point in item["footprint"]])
            if any(polygon.intersection(existing).area / max(polygon.area, 1) > 0.88 for existing in polygons):
                continue
            selected.append(item)
            polygons.append(polygon)
            if len(selected) >= 500:
                break
        return selected

    def _dimension_observations(self, blocks: list[dict[str, Any]], segments: list[Segment]) -> list[dict[str, Any]]:
        observations: list[dict[str, Any]] = []
        for block in blocks:
            matches = self._dimension_values(str(block["text"]))
            if len(matches) != 1:
                continue
            value = float(matches[0][1])
            if not 300 <= value <= 30000:
                continue
            point = (float(block["x"]), float(block["y"]))
            nearest: tuple[float, Segment] | None = None
            for segment in segments:
                if segment.length < 12 or segment.length > 1000:
                    continue
                distance = segment.line.distance(fitz_to_shapely_point(point))
                if distance > 35:
                    continue
                score = distance + (0 if segment.orientation in {"horizontal", "vertical"} else 20)
                if nearest is None or score < nearest[0]:
                    nearest = (score, segment)
            if nearest is None:
                continue
            segment = nearest[1]
            suggested = value / segment.length if segment.length else None
            if not suggested or not 0.05 <= suggested <= 500:
                continue
            confidence = max(0.25, min(0.9, 0.9 - nearest[0] / 60.0))
            observations.append({
                "label_text": str(block["text"]).strip(),
                "value_mm": value,
                "orientation": segment.orientation,
                "point_a": {"x": segment.start[0], "y": segment.start[1]},
                "point_b": {"x": segment.end[0], "y": segment.end[1]},
                "drawing_distance": segment.length,
                "suggested_mm_per_pixel": suggested,
                "confidence": confidence,
            })
        # Keep a coherent cluster around the median suggestion.
        if len(observations) >= 3:
            values = sorted(float(item["suggested_mm_per_pixel"]) for item in observations)
            median = values[len(values) // 2]
            observations = [
                item for item in observations
                if abs(float(item["suggested_mm_per_pixel"]) - median) / max(median, 1e-6) <= 0.18
            ]
        observations.sort(key=lambda item: float(item["confidence"]), reverse=True)
        return observations[:20]

    @classmethod
    def _dimension_values(cls, text: str) -> list[tuple[str, float]]:
        """Parse metric and architectural feet/inches dimensions as mm."""
        value = str(text or "").upper()
        if re.search(r"\b(?:FLOOR\s+)?AREA\b|\bSQ\.?\s*(?:FT|M)\b", value):
            return []
        output: list[tuple[str, float]] = []
        occupied: list[tuple[int, int]] = []
        for match in cls._imperial_dimension.finditer(value):
            # A leading plus sign denotes a level/elevation on architectural
            # plans (for example +13'-6"), not a measured room side.
            if value[:match.start()].rstrip().endswith("+"):
                continue
            feet = float(match.group(1) or 0)
            inches = float(match.group(2) or 0)
            output.append((match.group(0), (feet * 12.0 + inches) * 25.4))
            occupied.append(match.span())
        for match in cls._metric_dimension.finditer(value):
            if value[:match.start()].rstrip().endswith("+"):
                continue
            number = float((match.group(1) or "0").replace(",", "."))
            unit = str(match.group(2) or "MM").upper()
            factor = {"MM": 1.0, "CM": 10.0, "M": 1000.0}[unit]
            output.append((match.group(0), number * factor))
            occupied.append(match.span())
        for match in cls._bare_metric_dimension.finditer(value):
            if any(start <= match.start() and match.end() <= end for start, end in occupied):
                continue
            if value[:match.start()].rstrip().endswith("+"):
                continue
            output.append((match.group(0), float(match.group(1))))
        return output

    @staticmethod
    def _map_point(point: tuple[float, float], clip: fitz.Rect, rotation: int) -> tuple[float, float]:
        u = (point[0] - clip.x0) / max(clip.width, 1e-6)
        v = (point[1] - clip.y0) / max(clip.height, 1e-6)
        if rotation == 90:
            u, v = 1.0 - v, u
            width, height = clip.height, clip.width
        elif rotation == 180:
            u, v = 1.0 - u, 1.0 - v
            width, height = clip.width, clip.height
        elif rotation == 270:
            u, v = v, 1.0 - u
            width, height = clip.height, clip.width
        else:
            width, height = clip.width, clip.height
        return u * width, v * height

    def _map_pair(self, first: tuple[float, float], second: tuple[float, float], clip: fitz.Rect, rotation: int):
        return self._map_point(first, clip, rotation), self._map_point(second, clip, rotation)

    @staticmethod
    def _parallel_distance(first: Segment, second: Segment) -> float:
        if first.orientation == "horizontal":
            return abs((first.start[1] + first.end[1]) / 2 - (second.start[1] + second.end[1]) / 2)
        return abs((first.start[0] + first.end[0]) / 2 - (second.start[0] + second.end[0]) / 2)

    @staticmethod
    def _overlap_ratio(first: Segment, second: Segment) -> float:
        if first.orientation == "horizontal":
            a0, a1 = sorted((first.start[0], first.end[0]))
            b0, b1 = sorted((second.start[0], second.end[0]))
        else:
            a0, a1 = sorted((first.start[1], first.end[1]))
            b0, b1 = sorted((second.start[1], second.end[1]))
        overlap = max(0.0, min(a1, b1) - max(a0, b0))
        return overlap / max(min(a1 - a0, b1 - b0), 1e-6)

    @staticmethod
    def _midline(first: Segment, second: Segment) -> LineString:
        if first.orientation == "horizontal":
            start = max(min(first.start[0], first.end[0]), min(second.start[0], second.end[0]))
            end = min(max(first.start[0], first.end[0]), max(second.start[0], second.end[0]))
            y = ((first.start[1] + first.end[1]) + (second.start[1] + second.end[1])) / 4
            return LineString([(start, y), (end, y)])
        start = max(min(first.start[1], first.end[1]), min(second.start[1], second.end[1]))
        end = min(max(first.start[1], first.end[1]), max(second.start[1], second.end[1]))
        x = ((first.start[0] + first.end[0]) + (second.start[0] + second.end[0])) / 4
        return LineString([(x, start), (x, end)])

    @staticmethod
    def _line_dict(line: LineString) -> dict[str, dict[str, float]]:
        coords = list(line.coords)
        return {
            "start": {"x": float(coords[0][0]), "y": float(coords[0][1])},
            "end": {"x": float(coords[-1][0]), "y": float(coords[-1][1])},
        }

    @staticmethod
    def _polygon_points(polygon: Polygon) -> list[dict[str, float]]:
        coords = list(polygon.exterior.coords)
        if coords and coords[0] == coords[-1]:
            coords.pop()
        return [{"x": float(x), "y": float(y)} for x, y in coords]

    @staticmethod
    def _serialize_segment(segment: Segment) -> dict[str, Any]:
        return {
            "start": {"x": segment.start[0], "y": segment.start[1]},
            "end": {"x": segment.end[0], "y": segment.end[1]},
            "width": segment.width,
            "orientation": segment.orientation,
        }


def fitz_to_shapely_point(point: tuple[float, float]):
    from shapely.geometry import Point
    return Point(point)


vector_floor_geometry_service = VectorFloorGeometryService()
