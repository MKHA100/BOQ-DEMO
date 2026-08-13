"use client";

import type { PointerEvent as ReactPointerEvent } from "react";
import type { Point } from "@/features/drawing/types";

function sourcePoint(event: ReactPointerEvent<SVGElement>): Point | null {
  const svg = event.currentTarget.ownerSVGElement;
  const matrix = svg?.getScreenCTM();
  if (!matrix) return null;
  return new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
}

export function RoomVertexEditor({
  points,
  selectedIndex,
  onSelect,
  onMove,
}: {
  points: Point[];
  selectedIndex: number | null;
  onSelect: (index: number) => void;
  onMove: (index: number, point: Point) => void;
}) {
  return (
    <g>
      {points.map((point, index) => (
        <circle
          key={`${index}-${point.x}-${point.y}`}
          cx={point.x}
          cy={point.y}
          r={selectedIndex === index ? 6 : 5}
          fill={selectedIndex === index ? "#0f172a" : "#2563eb"}
          stroke="white"
          strokeWidth={2}
          vectorEffect="non-scaling-stroke"
          className="cursor-move"
          onClick={(event) => { event.stopPropagation(); onSelect(index); }}
          onPointerDown={(event) => {
            event.stopPropagation();
            onSelect(index);
            event.currentTarget.setPointerCapture(event.pointerId);
          }}
          onPointerMove={(event) => {
            if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
            const pointValue = sourcePoint(event);
            if (pointValue) onMove(index, pointValue);
          }}
          onPointerUp={(event) => {
            if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
          }}
        />
      ))}
    </g>
  );
}
