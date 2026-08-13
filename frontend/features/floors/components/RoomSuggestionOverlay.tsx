"use client";

import type { RoomSuggestion } from "../types";

export function RoomSuggestionOverlay({ suggestion, selected, onSelect }: { suggestion: RoomSuggestion; selected: boolean; onSelect: () => void }) {
  const points = suggestion.polygon?.points || [];
  if (points.length < 3) return null;
  return (
    <polygon
      points={points.map((point) => `${point.x},${point.y}`).join(" ")}
      fill={selected ? "rgba(245,158,11,.12)" : "rgba(245,158,11,.04)"}
      stroke="#d97706"
      strokeWidth={selected ? 2.5 : 1.5}
      strokeDasharray="7 5"
      vectorEffect="non-scaling-stroke"
      className="cursor-pointer"
      onClick={(event) => { event.stopPropagation(); onSelect(); }}
    />
  );
}
