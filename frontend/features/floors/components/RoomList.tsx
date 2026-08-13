"use client";

import type { Room, RoomFloor } from "../types";

export type RoomFilter = "all" | "needs_review" | "confirmed";

function stage(room: Room) {
  if (room.excluded) return { text: "Excluded", cls: "bg-slate-100 text-slate-600" };
  if (room.status === "confirmed" || room.processing_stage === "confirmed") return { text: "Confirmed", cls: "bg-emerald-50 text-emerald-700" };
  if (room.processing_stage === "detected") return { text: "Detected", cls: "bg-blue-50 text-blue-700" };
  if (room.processing_stage === "interpreting") return { text: "Interpreting", cls: "bg-violet-50 text-violet-700" };
  if (room.processing_stage === "correcting") return { text: "Correcting", cls: "bg-sky-50 text-sky-700" };
  if (room.processing_stage === "corrected" && room.measurement_status === "correct") return { text: "Correct", cls: "bg-emerald-50 text-emerald-700" };
  return { text: "Check", cls: "bg-amber-50 text-amber-700" };
}

export function RoomList({
  floors,
  floorId,
  rooms,
  filter,
  selectedId,
  onFloor,
  onFilter,
  onSelect,
}: {
  floors: RoomFloor[];
  floorId: string | null;
  rooms: Room[];
  filter: RoomFilter;
  selectedId: string | null;
  onFloor: (floorId: string) => void;
  onFilter: (filter: RoomFilter) => void;
  onSelect: (roomId: string) => void;
}) {
  const visible = rooms.filter((room) => {
    if (filter === "needs_review") return !room.excluded && room.status === "needs_review";
    if (filter === "confirmed") return !room.excluded && room.status === "confirmed";
    return true;
  });
  return (
    <aside className="flex min-h-0 flex-col border-r border-slate-200 bg-white">
      <div className="border-b border-slate-200 p-4">
        <label className="block text-xs font-semibold uppercase tracking-[.14em] text-slate-400">Floor</label>
        <select className="input mt-2 w-full" value={floorId || ""} onChange={(event) => onFloor(event.target.value)}>
          {floors.map((floor) => <option key={floor.id} value={floor.id}>{floor.name}</option>)}
        </select>
      </div>
      <div className="grid grid-cols-3 gap-1 border-b border-slate-200 p-3 text-xs">
        {(["all", "needs_review", "confirmed"] as RoomFilter[]).map((value) => (
          <button
            key={value}
            type="button"
            className={filter === value ? "rounded-lg bg-slate-900 px-2 py-2 font-semibold text-white" : "rounded-lg px-2 py-2 font-medium text-slate-600 hover:bg-slate-100"}
            onClick={() => onFilter(value)}
          >
            {value === "all" ? "All" : value === "needs_review" ? "Review" : "Confirmed"}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <p className="mb-2 text-xs font-semibold uppercase tracking-[.14em] text-slate-400">Rooms</p>
        <div className="space-y-2">
          {visible.map((room) => {
            const badge = stage(room);
            return (
            <button
              key={room.id}
              type="button"
              onClick={() => onSelect(room.id)}
              className={selectedId === room.id ? "w-full rounded-xl border border-blue-300 bg-blue-50 p-3 text-left" : "w-full rounded-xl border border-slate-200 p-3 text-left hover:border-blue-200"}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-slate-900">{room.friendly_number} {(room.name || "Room").toUpperCase()}</p>
                  <p className="mt-1 truncate text-xs text-slate-500">{room.floor_finish || room.room_type || "Finish not assigned"}</p>
                </div>
                <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${badge.cls}`}>
                  {badge.text}
                </span>
              </div>
              <p className="mt-2 text-xs font-semibold text-slate-700">{room.area_m2 == null ? "Area not ready" : `${room.area_m2.toFixed(2)} m²`}</p>
            </button>
            );
          })}
          {!visible.length ? <p className="rounded-xl border border-dashed border-slate-200 p-4 text-center text-sm text-slate-500">No rooms in this view.</p> : null}
        </div>
      </div>
    </aside>
  );
}
