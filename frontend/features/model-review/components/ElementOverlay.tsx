"use client";

import { useRef } from "react";
import type { Point, Rect } from "@/features/drawing/types";
import type { ElementLabelPlacement } from "../labelLayout";
import type { ReviewElement } from "../types";

type DragMode = "move" | "resize";
type DragState = { pointerId: number; mode: DragMode; start: Point; geometry: Rect };

function sourcePoint(event: React.PointerEvent<SVGElement>): Point | null {
  const svg = event.currentTarget.ownerSVGElement;
  const matrix = svg?.getScreenCTM();
  if (!matrix) return null;
  const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
  return { x: point.x, y: point.y };
}

const colors = {
  door: { stroke: "#2563eb", soft: "#dbeafe" },
  window: { stroke: "#0f766e", soft: "#ccfbf1" },
  wall: { stroke: "#7c3aed", soft: "#ede9fe" },
} as const;

export function ElementOverlay({
  element,
  selected,
  editing,
  zoom,
  label,
  onSelect,
  onGeometryChange,
}: {
  element: ReviewElement;
  selected: boolean;
  editing: boolean;
  zoom: number;
  label: ElementLabelPlacement | undefined;
  onSelect: () => void;
  onGeometryChange: (geometry: Rect) => void;
}) {
  const drag = useRef<DragState | null>(null);
  const geometry = element.geometry;
  const palette = colors[element.element_type];
  const stroke = element.excluded ? "#94a3b8" : palette.stroke;
  const handleSize = Math.max(1.8, 12 / Math.max(zoom, 0.1));

  function startDrag(event: React.PointerEvent<SVGElement>, mode: DragMode) {
    event.stopPropagation();
    onSelect();
    if (!selected || !editing) return;
    const point = sourcePoint(event);
    if (!point) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { pointerId: event.pointerId, mode, start: point, geometry: { ...geometry } };
  }

  function move(event: React.PointerEvent<SVGElement>) {
    const state = drag.current;
    if (!state || state.pointerId !== event.pointerId) return;
    event.stopPropagation();
    const point = sourcePoint(event);
    if (!point) return;
    const dx = point.x - state.start.x;
    const dy = point.y - state.start.y;
    if (state.mode === "move") {
      onGeometryChange({
        ...state.geometry,
        x: Math.max(0, state.geometry.x + dx),
        y: Math.max(0, state.geometry.y + dy),
      });
      return;
    }
    onGeometryChange({
      ...state.geometry,
      width: Math.max(3, state.geometry.width + dx),
      height: Math.max(3, state.geometry.height + dy),
    });
  }

  function end(event: React.PointerEvent<SVGElement>) {
    if (drag.current?.pointerId === event.pointerId) drag.current = null;
    event.stopPropagation();
  }

  const numberText = String(element.item_number).padStart(3, "0");
  const detailedText = `${numberText}${element.type_code || element.tag_text ? ` · ${element.type_code || element.tag_text}` : ""}`;
  const labelText = label?.detailed ? detailedText : numberText;

  return (
    <g opacity={element.excluded ? 0.42 : 1}>
      <rect
        x={geometry.x}
        y={geometry.y}
        width={geometry.width}
        height={geometry.height}
        fill={selected ? palette.soft : "transparent"}
        fillOpacity={selected ? 0.07 : 0}
        stroke="white"
        strokeWidth={selected ? 4 : 3}
        vectorEffect="non-scaling-stroke"
        pointerEvents="none"
      />
      <rect
        x={geometry.x}
        y={geometry.y}
        width={geometry.width}
        height={geometry.height}
        fill="transparent"
        stroke={stroke}
        strokeWidth={selected ? 2.1 : 1.15}
        strokeDasharray={element.excluded ? "5 4" : undefined}
        vectorEffect="non-scaling-stroke"
        pointerEvents={element.element_type === "wall" ? "stroke" : "all"}
        onClick={(event) => { event.stopPropagation(); onSelect(); }}
        onPointerDown={(event) => startDrag(event, "move")}
        onPointerMove={move}
        onPointerUp={end}
        onPointerCancel={end}
        className={selected && editing ? "cursor-move" : "cursor-pointer"}
      >
        <title>{`${element.display_number} · ${element.element_type}${element.type_code ? ` · ${element.type_code}` : ""}`}</title>
      </rect>

      {label?.visible ? (
        <g onClick={(event) => { event.stopPropagation(); onSelect(); }} className="cursor-pointer">
          <line
            x1={label.anchorX}
            y1={label.anchorY}
            x2={label.labelX}
            y2={label.labelY}
            stroke="white"
            strokeWidth={3.5}
            vectorEffect="non-scaling-stroke"
            pointerEvents="none"
          />
          <line
            x1={label.anchorX}
            y1={label.anchorY}
            x2={label.labelX}
            y2={label.labelY}
            stroke={stroke}
            strokeWidth={0.9}
            vectorEffect="non-scaling-stroke"
            pointerEvents="none"
          />
          <rect
            x={label.x}
            y={label.y}
            width={label.width}
            height={label.height}
            rx={label.height * 0.28}
            fill="white"
            fillOpacity={0.97}
            stroke={selected ? "#0f172a" : stroke}
            strokeWidth={selected ? 1.5 : 1}
            vectorEffect="non-scaling-stroke"
          />
          <text
            x={label.x + label.width / 2}
            y={label.y + label.height * 0.67}
            textAnchor="middle"
            fill={selected ? "#0f172a" : stroke}
            fontSize={label.height * 0.51}
            fontWeight={800}
            pointerEvents="none"
          >
            {labelText}
          </text>
          <title>{`${element.display_number} · ${element.type_code || element.tag_text || element.element_type}`}</title>
        </g>
      ) : null}

      {selected && editing ? (
        <g>
          <circle
            cx={geometry.x + geometry.width}
            cy={geometry.y + geometry.height}
            r={handleSize / 2}
            fill="white"
            stroke={stroke}
            strokeWidth={1.8}
            vectorEffect="non-scaling-stroke"
            className="cursor-se-resize"
            onPointerDown={(event) => startDrag(event, "resize")}
            onPointerMove={move}
            onPointerUp={end}
            onPointerCancel={end}
          />
        </g>
      ) : null}
    </g>
  );
}
