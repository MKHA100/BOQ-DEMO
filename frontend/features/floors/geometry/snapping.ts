import type { Point } from "@/features/drawing/types";

export function snapPointToAxis(point: Point, anchor: Point, tolerance = 8): Point {
  const next = { ...point };
  if (Math.abs(point.x - anchor.x) <= tolerance) next.x = anchor.x;
  if (Math.abs(point.y - anchor.y) <= tolerance) next.y = anchor.y;
  return next;
}

export function straightenPolygon(points: Point[], toleranceDegrees = 5): Point[] {
  const next = points.map((point) => ({ ...point }));
  for (let index = 0; index < next.length; index += 1) {
    const second = (index + 1) % next.length;
    const dx = next[second].x - next[index].x;
    const dy = next[second].y - next[index].y;
    const angle = Math.abs(Math.atan2(dy, dx) * 180 / Math.PI) % 180;
    if (Math.min(angle, Math.abs(180 - angle)) <= toleranceDegrees) {
      const y = (next[index].y + next[second].y) / 2;
      next[index].y = y;
      next[second].y = y;
    } else if (Math.abs(angle - 90) <= toleranceDegrees) {
      const x = (next[index].x + next[second].x) / 2;
      next[index].x = x;
      next[second].x = x;
    }
  }
  return next;
}
