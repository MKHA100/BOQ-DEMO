import type { Point } from "@/features/drawing/types";

export function polygonArea(points: Point[]): number {
  if (points.length < 3) return 0;
  let total = 0;
  for (let index = 0; index < points.length; index += 1) {
    const current = points[index];
    const next = points[(index + 1) % points.length];
    total += current.x * next.y - next.x * current.y;
  }
  return Math.abs(total) / 2;
}

export function polygonPerimeter(points: Point[]): number {
  return points.reduce((total, current, index) => {
    const next = points[(index + 1) % points.length];
    return total + Math.hypot(next.x - current.x, next.y - current.y);
  }, 0);
}

export function boundingDimensions(points: Point[]): { width: number; length: number } {
  if (!points.length) return { width: 0, length: 0 };
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const first = Math.max(...xs) - Math.min(...xs);
  const second = Math.max(...ys) - Math.min(...ys);
  return { width: Math.min(first, second), length: Math.max(first, second) };
}

export function insertPoint(points: Point[], edgeIndex: number, point: Point): Point[] {
  const next = [...points];
  next.splice(Math.max(0, Math.min(edgeIndex + 1, next.length)), 0, point);
  return next;
}

export function deletePoint(points: Point[], pointIndex: number): Point[] {
  if (points.length <= 3) return points;
  return points.filter((_, index) => index !== pointIndex);
}

export function moveEdge(points: Point[], edgeIndex: number, delta: Point): Point[] {
  if (!points.length) return points;
  const next = points.map((point) => ({ ...point }));
  const second = (edgeIndex + 1) % next.length;
  for (const index of new Set([edgeIndex, second])) {
    next[index] = { x: next[index].x + delta.x, y: next[index].y + delta.y };
  }
  return next;
}

export function makeRectangle(points: Point[]): Point[] {
  if (!points.length) return points;
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  return [
    { x: minX, y: minY },
    { x: maxX, y: minY },
    { x: maxX, y: maxY },
    { x: minX, y: maxY },
  ];
}

export function simplifyPoints(points: Point[], angleTolerance = 3, minimumEdge = 4): Point[] {
  if (points.length <= 4) return points;
  const result: Point[] = [];
  for (let index = 0; index < points.length; index += 1) {
    const previous = points[(index - 1 + points.length) % points.length];
    const current = points[index];
    const next = points[(index + 1) % points.length];
    const first = { x: previous.x - current.x, y: previous.y - current.y };
    const second = { x: next.x - current.x, y: next.y - current.y };
    const denominator = Math.max(Math.hypot(first.x, first.y) * Math.hypot(second.x, second.y), 1e-9);
    const cosine = Math.max(-1, Math.min(1, (first.x * second.x + first.y * second.y) / denominator));
    const angle = Math.acos(cosine) * 180 / Math.PI;
    const short = Math.hypot(current.x - previous.x, current.y - previous.y) < minimumEdge
      && Math.hypot(next.x - current.x, next.y - current.y) < minimumEdge;
    if (Math.abs(180 - angle) <= angleTolerance || short) continue;
    result.push(current);
  }
  return result.length >= 3 ? result : points;
}

export function nearestEdge(points: Point[], point: Point): number {
  let bestIndex = 0;
  let bestDistance = Number.POSITIVE_INFINITY;
  points.forEach((start, index) => {
    const end = points[(index + 1) % points.length];
    const distance = pointToSegmentDistance(point, start, end);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIndex = index;
    }
  });
  return bestIndex;
}

function pointToSegmentDistance(point: Point, start: Point, end: Point): number {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  if (!dx && !dy) return Math.hypot(point.x - start.x, point.y - start.y);
  const t = Math.max(0, Math.min(1, ((point.x - start.x) * dx + (point.y - start.y) * dy) / (dx * dx + dy * dy)));
  return Math.hypot(point.x - (start.x + t * dx), point.y - (start.y + t * dy));
}
