import type { Rect } from "@/features/drawing/types";
import type { LabelMode, ReviewElement } from "./types";

export type ElementLabelPlacement = {
  elementId: string;
  visible: boolean;
  x: number;
  y: number;
  width: number;
  height: number;
  anchorX: number;
  anchorY: number;
  labelX: number;
  labelY: number;
  detailed: boolean;
};

type LayoutOptions = {
  drawingWidth: number;
  drawingHeight: number;
  zoom: number;
  mode: LabelMode;
  selectedId: string | null;
};

const area = (rect: Rect) => Math.max(0, rect.width) * Math.max(0, rect.height);

function intersection(a: Rect, b: Rect): number {
  const left = Math.max(a.x, b.x);
  const top = Math.max(a.y, b.y);
  const right = Math.min(a.x + a.width, b.x + b.width);
  const bottom = Math.min(a.y + a.height, b.y + b.height);
  return Math.max(0, right - left) * Math.max(0, bottom - top);
}

function clampRect(rect: Rect, width: number, height: number): Rect {
  return {
    ...rect,
    x: Math.max(0, Math.min(width - rect.width, rect.x)),
    y: Math.max(0, Math.min(height - rect.height, rect.y)),
  };
}

function nearestAnchor(element: Rect, label: Rect): { anchorX: number; anchorY: number; labelX: number; labelY: number } {
  const elementCenterX = element.x + element.width / 2;
  const elementCenterY = element.y + element.height / 2;
  const labelCenterX = label.x + label.width / 2;
  const labelCenterY = label.y + label.height / 2;
  const dx = labelCenterX - elementCenterX;
  const dy = labelCenterY - elementCenterY;

  if (Math.abs(dx / Math.max(element.width, 1)) > Math.abs(dy / Math.max(element.height, 1))) {
    return {
      anchorX: dx >= 0 ? element.x + element.width : element.x,
      anchorY: Math.max(element.y, Math.min(element.y + element.height, labelCenterY)),
      labelX: dx >= 0 ? label.x : label.x + label.width,
      labelY: labelCenterY,
    };
  }
  return {
    anchorX: Math.max(element.x, Math.min(element.x + element.width, labelCenterX)),
    anchorY: dy >= 0 ? element.y + element.height : element.y,
    labelX: labelCenterX,
    labelY: dy >= 0 ? label.y : label.y + label.height,
  };
}

function shouldShow(element: ReviewElement, mode: LabelMode, zoom: number, selectedId: string | null): boolean {
  if (element.id === selectedId) return true;
  if (mode === "selected") return false;
  if (mode === "all") return true;
  if (element.element_type === "wall") return zoom >= 1.55;
  return true;
}

export function layoutElementLabels(
  elements: ReviewElement[],
  { drawingWidth, drawingHeight, zoom, mode, selectedId }: LayoutOptions,
): Map<string, ElementLabelPlacement> {
  const placements = new Map<string, ElementLabelPlacement>();
  const placed: Rect[] = [];
  const drawingMin = Math.max(100, Math.min(drawingWidth, drawingHeight));
  const inverseZoom = 1 / Math.max(0.55, zoom);
  const baseHeight = Math.max(8, drawingMin * 0.021) * inverseZoom;
  const gap = baseHeight * 0.42;
  const geometry = elements.map((item) => item.geometry);

  const ordered = [...elements].sort((a, b) => {
    if (a.id === selectedId) return -1;
    if (b.id === selectedId) return 1;
    const priority = { door: 0, window: 1, wall: 2 } as const;
    return priority[a.element_type] - priority[b.element_type] || a.item_number - b.item_number;
  });

  for (const element of ordered) {
    const visible = shouldShow(element, mode, zoom, selectedId);
    if (!visible) {
      placements.set(element.id, {
        elementId: element.id,
        visible: false,
        x: 0,
        y: 0,
        width: 0,
        height: 0,
        anchorX: 0,
        anchorY: 0,
        labelX: 0,
        labelY: 0,
        detailed: false,
      });
      continue;
    }

    const detailed = element.id === selectedId;
    const labelHeight = baseHeight * (detailed ? 1.12 : 1);
    const labelWidth = labelHeight * (detailed ? 5.2 : 2.65);
    const box = element.geometry;
    const candidates: Rect[] = [
      { x: box.x + box.width / 2 - labelWidth / 2, y: box.y - gap - labelHeight, width: labelWidth, height: labelHeight },
      { x: box.x + box.width / 2 - labelWidth / 2, y: box.y + box.height + gap, width: labelWidth, height: labelHeight },
      { x: box.x + box.width + gap, y: box.y + box.height / 2 - labelHeight / 2, width: labelWidth, height: labelHeight },
      { x: box.x - gap - labelWidth, y: box.y + box.height / 2 - labelHeight / 2, width: labelWidth, height: labelHeight },
      { x: box.x + box.width + gap, y: box.y - gap - labelHeight, width: labelWidth, height: labelHeight },
      { x: box.x - gap - labelWidth, y: box.y - gap - labelHeight, width: labelWidth, height: labelHeight },
      { x: box.x + box.width + gap, y: box.y + box.height + gap, width: labelWidth, height: labelHeight },
      { x: box.x - gap - labelWidth, y: box.y + box.height + gap, width: labelWidth, height: labelHeight },
    ].map((candidate) => clampRect(candidate, drawingWidth, drawingHeight));

    let best = candidates[0];
    let bestScore = Number.POSITIVE_INFINITY;
    for (const candidate of candidates) {
      const labelArea = Math.max(1, area(candidate));
      const labelOverlap = placed.reduce((sum, existing) => sum + intersection(candidate, existing) / labelArea, 0);
      const geometryOverlap = geometry.reduce((sum, existing) => sum + intersection(candidate, existing) / labelArea, 0);
      const distance = Math.hypot(
        candidate.x + candidate.width / 2 - (box.x + box.width / 2),
        candidate.y + candidate.height / 2 - (box.y + box.height / 2),
      ) / drawingMin;
      const score = labelOverlap * 1000 + geometryOverlap * 55 + distance;
      if (score < bestScore) {
        best = candidate;
        bestScore = score;
      }
    }

    const anchor = nearestAnchor(box, best);
    placements.set(element.id, {
      elementId: element.id,
      visible: true,
      ...best,
      ...anchor,
      detailed,
    });
    placed.push({
      x: best.x - gap * 0.35,
      y: best.y - gap * 0.35,
      width: best.width + gap * 0.7,
      height: best.height + gap * 0.7,
    });
  }

  return placements;
}
