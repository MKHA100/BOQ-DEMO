"use client";

import type { Room } from "../types";

function polygonValue(points: Array<{ x: number; y: number }>) {
  return points.map((point) => `${point.x},${point.y}`).join(" ");
}

export function RoomOverlay({ room, selected, onSelect }: {
  room: Room;
  selected: boolean;
  onSelect: () => void;
}) {
  const points = room.display_polygon?.points?.length
    ? room.display_polygon.points
    : room.geometry?.points || [];
  const modelPoints = room.model_polygon?.points || [];
  if (points.length < 3) return null;

  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const minX = Math.min(...xs); const maxX = Math.max(...xs);
  const minY = Math.min(...ys); const maxY = Math.max(...ys);
  const center = { x: (minX + maxX) / 2, y: (minY + maxY) / 2 };
  const small = (maxX - minX) < 85 || (maxY - minY) < 45;
  const label = (room.name || room.friendly_number).toUpperCase();
  const labelX = small ? maxX + 8 : center.x;
  const labelY = small ? minY + 12 : center.y;
  const status = room.measurement_status === "correct" ? "correct" : room.measurement_status === "missing_scale" ? "scale" : "check";
  const provisional = room.processing_stage === "detected" || room.boundary_source === "model_only";
  const stroke = room.excluded ? "#94a3b8" : selected ? "#2563eb" : status === "correct" ? "#0891b2" : status === "scale" ? "#dc2626" : "#d97706";
  const showModelEvidence = selected && modelPoints.length >= 3 && !provisional && room.boundary_source !== "user";
  const showLabel = selected || !small;

  return (
    <g onClick={(event) => { event.stopPropagation(); onSelect(); }}>
      {showModelEvidence ? (
        <polygon
          points={polygonValue(modelPoints)}
          fill="rgba(245,158,11,.025)"
          stroke="#f59e0b"
          strokeWidth={1.1}
          strokeDasharray="6 5"
          vectorEffect="non-scaling-stroke"
          pointerEvents="none"
        />
      ) : null}
      <polygon
        points={polygonValue(points)}
        fill={room.excluded ? "rgba(148,163,184,.05)" : room.is_finish_zone ? "rgba(168,85,247,.08)" : selected ? "rgba(37,99,235,.10)" : "rgba(14,116,144,.04)"}
        stroke={room.is_finish_zone ? "#9333ea" : provisional ? "#d97706" : stroke}
        strokeWidth={selected ? 2.5 : 1.5}
        strokeDasharray={room.excluded || room.is_finish_zone || provisional ? "7 5" : undefined}
        vectorEffect="non-scaling-stroke"
        className="cursor-pointer"
      />
      {showLabel ? <g pointerEvents="none">
        {small ? <line x1={center.x} y1={center.y} x2={labelX} y2={labelY} stroke={stroke} strokeWidth={1} vectorEffect="non-scaling-stroke" /> : null}
        <rect x={labelX - Math.min(44, Math.max(24, label.length * 3))} y={labelY - 9} width={Math.min(88, Math.max(48, label.length * 6))} height={18} rx={7} fill="white" fillOpacity={0.9} stroke={room.is_finish_zone ? "#9333ea" : provisional ? "#d97706" : stroke} strokeWidth={0.8} vectorEffect="non-scaling-stroke" />
        <text x={labelX} y={labelY + 3} textAnchor="middle" fontSize={8} fontWeight={700} fill="#0f172a" vectorEffect="non-scaling-stroke">{label}</text>
      </g> : null}
      {room.cutouts?.map((cutout) => (
        <polygon key={cutout.id} points={polygonValue(cutout.geometry.points)} fill="rgba(248,113,113,.12)" stroke="#ef4444" strokeDasharray="5 3" vectorEffect="non-scaling-stroke" />
      ))}
    </g>
  );
}
