"use client";

import { useRef } from "react";
import type { Point } from "@/features/drawing/types";

export function RoomEdgeEditor({
  points,
  mode,
  selectedIndex,
  onSelect,
  onAddPoint,
  onMove,
}: {
  points: Point[];
  mode: "select" | "add" | "move";
  selectedIndex: number | null;
  onSelect: (index: number) => void;
  onAddPoint: (index: number, point: Point) => void;
  onMove: (index: number, delta: Point) => void;
}) {
  const origins = useRef<Record<number, Point>>({});
  return (
    <g>
      {points.map((start, index) => {
        const end = points[(index + 1) % points.length];
        return (
          <line
            key={index}
            x1={start.x}
            y1={start.y}
            x2={end.x}
            y2={end.y}
            stroke={selectedIndex === index ? "#0f172a" : "transparent"}
            strokeWidth={selectedIndex === index ? 3 : 14}
            vectorEffect="non-scaling-stroke"
            className={mode === "add" ? "cursor-crosshair" : mode === "move" ? "cursor-move" : "cursor-pointer"}
            onClick={(event) => {
              event.stopPropagation();
              onSelect(index);
              if (mode !== "add") return;
              const svg = event.currentTarget.ownerSVGElement;
              const matrix = svg?.getScreenCTM();
              if (!matrix) return;
              const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
              onAddPoint(index, point);
            }}
            onPointerDown={(event) => {
              if (mode !== "move") return;
              event.stopPropagation();
              onSelect(index);
              const svg = event.currentTarget.ownerSVGElement;
              const matrix = svg?.getScreenCTM();
              if (!matrix) return;
              origins.current[event.pointerId] = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
              event.currentTarget.setPointerCapture(event.pointerId);
            }}
            onPointerMove={(event) => {
              if (mode !== "move" || !event.currentTarget.hasPointerCapture(event.pointerId)) return;
              const origin = origins.current[event.pointerId];
              const svg = event.currentTarget.ownerSVGElement;
              const matrix = svg?.getScreenCTM();
              if (!origin || !matrix) return;
              const current = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
              onMove(index, { x: current.x - origin.x, y: current.y - origin.y });
              origins.current[event.pointerId] = current;
            }}
            onPointerUp={(event) => {
              delete origins.current[event.pointerId];
              if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
            }}
          />
        );
      })}
    </g>
  );
}
