"use client";

import { useRef, useState } from "react";
import type { Point } from "@/features/drawing/types";
import type { Centerline, Wall } from "../types";

type DragTarget = "line" | "start" | "end";
type DragState = {
  target: DragTarget;
  point: Point;
  line: Centerline;
};

const SNAP_DISTANCE = 12;

function nearestSnap(point: Point, candidates: Point[]): Point | null {
  let nearest: Point | null = null;
  let distance = SNAP_DISTANCE;
  for (const candidate of candidates) {
    const next = Math.hypot(point.x - candidate.x, point.y - candidate.y);
    if (next <= distance) {
      nearest = candidate;
      distance = next;
    }
  }
  return nearest;
}

export function WallOverlay({
  wall,
  selected,
  edit,
  showIssues,
  mmPerPixel,
  snapPoints,
  onSelect,
  onChange,
}: {
  wall: Wall;
  selected: boolean;
  edit: boolean;
  showIssues: boolean;
  mmPerPixel: number | null;
  snapPoints: Point[];
  onSelect: () => void;
  onChange: (line: Centerline) => void;
}) {
  const dragRef = useRef<DragState | null>(null);
  const [dragTarget, setDragTarget] = useState<DragTarget | null>(null);
  const [snapTarget, setSnapTarget] = useState<Point | null>(null);
  const line = wall.centerline;
  const warnings = (wall.validation_warnings || []).filter(
    (warning) => typeof warning !== "string" && warning.severity === "error",
  );
  const hasErrors = warnings.some((warning) => typeof warning !== "string" && warning.severity === "error");
  const hasWarnings = showIssues && Boolean(warnings.length);
  const warningColor = hasErrors ? "#dc2626" : "#d97706";
  const centerlineStroke = selected
    ? "#f59e0b"
    : hasWarnings
      ? warningColor
      : wall.classification === "external"
        ? "#1d4ed8"
        : "#475569";
  const thicknessPixels = wall.thickness_mm && mmPerPixel
    ? Math.max(4, Math.min(80, wall.thickness_mm / mmPerPixel))
    : wall.classification === "external" ? 8 : 6;

  function sourceDelta(event: React.PointerEvent<SVGElement>, origin: Point): Point | null {
    const svg = event.currentTarget.ownerSVGElement;
    const matrix = svg?.getScreenCTM();
    if (!matrix) return null;
    const a = new DOMPoint(origin.x, origin.y).matrixTransform(matrix.inverse());
    const b = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
    return { x: b.x - a.x, y: b.y - a.y };
  }

  function beginDrag(target: DragTarget, event: React.PointerEvent<SVGElement>) {
    event.stopPropagation();
    onSelect();
    if (!edit) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      target,
      point: { x: event.clientX, y: event.clientY },
      line,
    };
    setDragTarget(target);
  }

  function move(event: React.PointerEvent<SVGElement>) {
    const drag = dragRef.current;
    if (!drag) return;
    const delta = sourceDelta(event, drag.point);
    if (!delta) return;

    if (drag.target === "line") {
      onChange({
        start: { x: drag.line.start.x + delta.x, y: drag.line.start.y + delta.y },
        end: { x: drag.line.end.x + delta.x, y: drag.line.end.y + delta.y },
      });
      setSnapTarget(null);
      return;
    }

    const original = drag.target === "start" ? drag.line.start : drag.line.end;
    const moved = { x: original.x + delta.x, y: original.y + delta.y };
    const snapped = nearestSnap(moved, snapPoints);
    const endpoint = snapped || moved;
    setSnapTarget(snapped);
    onChange(drag.target === "start"
      ? { start: endpoint, end: drag.line.end }
      : { start: drag.line.start, end: endpoint });
  }

  function finish(event: React.PointerEvent<SVGElement>) {
    dragRef.current = null;
    setDragTarget(null);
    setSnapTarget(null);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  return (
    <g onClick={(event) => { event.stopPropagation(); onSelect(); }}>
      <line
        x1={line.start.x}
        y1={line.start.y}
        x2={line.end.x}
        y2={line.end.y}
        stroke={wall.classification === "external" ? "#2563eb" : "#64748b"}
        strokeWidth={thicknessPixels}
        strokeOpacity={selected ? 0.24 : 0.14}
        pointerEvents="none"
      />
      <line
        x1={line.start.x}
        y1={line.start.y}
        x2={line.end.x}
        y2={line.end.y}
        stroke="transparent"
        strokeWidth={18}
        vectorEffect="non-scaling-stroke"
        className={edit ? "cursor-move" : "cursor-pointer"}
        onPointerDown={(event) => beginDrag("line", event)}
        onPointerMove={move}
        onPointerUp={finish}
        onPointerCancel={finish}
      />
      <line
        x1={line.start.x}
        y1={line.start.y}
        x2={line.end.x}
        y2={line.end.y}
        stroke={centerlineStroke}
        strokeWidth={selected ? 3 : 2}
        strokeDasharray={wall.boundary_role === "outer" || hasWarnings ? "8 5" : undefined}
        vectorEffect="non-scaling-stroke"
        pointerEvents="none"
      />
      {hasWarnings ? (
        <g transform={`translate(${(line.start.x + line.end.x) / 2} ${(line.start.y + line.end.y) / 2})`} pointerEvents="none">
          <circle r={7} fill={warningColor} stroke="white" strokeWidth={2} vectorEffect="non-scaling-stroke" />
          <path d="M0 -3.5V1 M0 3.5V4" stroke="white" strokeWidth={1.8} strokeLinecap="round" vectorEffect="non-scaling-stroke" />
        </g>
      ) : null}
      {selected && edit ? (
        <>
          {snapTarget ? <circle cx={snapTarget.x} cy={snapTarget.y} r={9} fill="none" stroke="#16a34a" strokeWidth={2} vectorEffect="non-scaling-stroke" pointerEvents="none" /> : null}
          <circle
            cx={line.start.x}
            cy={line.start.y}
            r={6}
            fill={dragTarget === "start" && snapTarget ? "#16a34a" : "#f59e0b"}
            stroke="white"
            strokeWidth={2}
            vectorEffect="non-scaling-stroke"
            className={edit ? "cursor-crosshair" : "cursor-pointer"}
            onPointerDown={(event) => beginDrag("start", event)}
            onPointerMove={move}
            onPointerUp={finish}
            onPointerCancel={finish}
          />
          <circle
            cx={line.end.x}
            cy={line.end.y}
            r={6}
            fill={dragTarget === "end" && snapTarget ? "#16a34a" : "#f59e0b"}
            stroke="white"
            strokeWidth={2}
            vectorEffect="non-scaling-stroke"
            className={edit ? "cursor-crosshair" : "cursor-pointer"}
            onPointerDown={(event) => beginDrag("end", event)}
            onPointerMove={move}
            onPointerUp={finish}
            onPointerCancel={finish}
          />
        </>
      ) : null}
    </g>
  );
}
