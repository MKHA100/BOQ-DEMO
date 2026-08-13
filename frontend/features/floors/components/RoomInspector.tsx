"use client";

import { useEffect, useState } from "react";
import { Button } from "@/shared/components/Button";
import type { GeometryRevision, Room, RoomPatch } from "../types";
import { RoomGeometryStatus } from "./RoomGeometryStatus";
import { RoomEditHistory } from "./RoomEditHistory";

const value = (number: number | null, unit: string) => number == null ? "—" : `${number.toFixed(2)} ${unit}`;

function measurementLabel(room: Room) {
  if (room.measurement_status === "correct") return { text: "Correct", cls: "bg-emerald-50 text-emerald-700" };
  if (room.measurement_status === "missing_scale") return { text: "Missing scale", cls: "bg-rose-50 text-rose-700" };
  if (room.measurement_status === "invalid") return { text: "Needs correction", cls: "bg-red-50 text-red-700" };
  return { text: "Check", cls: "bg-amber-50 text-amber-700" };
}

export function RoomInspector({
  room, rooms, saving, revisions, onSave, onEdit, onConfirm, onExclude, onDelete,
  onSplitLine, onAddZone, onAddCutout, onMerge, onRestore, onRestoreRevision, onDeleteCutout,
  onResetToModel, onResetToCorrected,
}: {
  room: Room | null;
  rooms: Room[];
  saving: boolean;
  revisions: GeometryRevision[];
  onSave: (patch: RoomPatch) => Promise<void>;
  onEdit: () => void;
  onConfirm: () => Promise<void>;
  onExclude: () => Promise<void>;
  onDelete: () => Promise<void>;
  onSplitLine: () => void;
  onAddZone: () => void;
  onAddCutout: () => void;
  onMerge: (roomId: string) => Promise<void>;
  onRestore: () => Promise<void>;
  onRestoreRevision: (revisionId: string) => Promise<void>;
  onDeleteCutout: (cutoutId: string) => Promise<void>;
  onResetToModel: () => Promise<void>;
  onResetToCorrected: () => Promise<void>;
}) {
  const [draft, setDraft] = useState<RoomPatch>({});
  const [mergeId, setMergeId] = useState("");
  useEffect(() => {
    setDraft(room ? {
      name: room.name, room_type: room.room_type, floor_type_code: room.floor_type_code,
      floor_finish: room.floor_finish, review_status: room.status,
      space_kind: room.space_kind as RoomPatch["space_kind"], include_in_boq: room.include_in_boq,
      open_plan: room.open_plan,
    } : {});
    setMergeId("");
  }, [room]);

  if (!room) return <div className="p-6 text-sm text-slate-500">Select a room to review it.</div>;
  const measurement = measurementLabel(room);

  return (
    <div className="space-y-4 p-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[.14em] text-slate-400">Selected {room.is_finish_zone ? "finish zone" : "room"}</p>
        <div className="mt-1 flex items-center justify-between gap-3">
          <h3 className="text-lg font-semibold">{room.friendly_number}</h3>
          <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${measurement.cls}`}>{measurement.text}</span>
        </div>
      </div>

      <label className="block text-sm font-medium">Name
        <input className="input mt-1 w-full" value={draft.name || ""} onChange={(event) => setDraft({ ...draft, name: event.target.value })} />
      </label>
      <label className="block text-sm font-medium">Type
        <input className="input mt-1 w-full" value={draft.room_type || ""} onChange={(event) => setDraft({ ...draft, room_type: event.target.value })} />
      </label>
      <div className="grid grid-cols-2 gap-3">
        <label className="block text-sm font-medium">Floor type
          <input className="input mt-1 w-full" value={draft.floor_type_code || ""} onChange={(event) => setDraft({ ...draft, floor_type_code: event.target.value })} />
        </label>
        <label className="block text-sm font-medium">Finish
          <input className="input mt-1 w-full" value={draft.floor_finish || ""} onChange={(event) => setDraft({ ...draft, floor_finish: event.target.value })} />
        </label>
      </div>
      <label className="block text-sm font-medium">Area type
        <select className="input mt-1 w-full" value={draft.space_kind || "internal"} onChange={(event) => setDraft({ ...draft, space_kind: event.target.value as RoomPatch["space_kind"], include_in_boq: !["void", "circulation"].includes(event.target.value) })}>
          <option value="internal">Internal room</option>
          <option value="external">Balcony / verandah</option>
          <option value="circulation">Stair / circulation</option>
          <option value="void">Void / shaft</option>
        </select>
      </label>

      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
        <div className="flex justify-between"><span>Area</span><strong>{value(room.area_m2, "m²")}</strong></div>
        <div className="mt-2 flex justify-between"><span>Perimeter</span><strong>{value(room.perimeter_m, "m")}</strong></div>
        <div className="mt-2 flex justify-between"><span>Width</span><strong>{value(room.measured_width_m, "m")}</strong></div>
        <div className="mt-2 flex justify-between"><span>Length</span><strong>{value(room.measured_length_m, "m")}</strong></div>
        <div className="mt-2 flex justify-between"><span>Printed dimensions</span><strong className="capitalize">{room.dimension_status || "Unknown"}</strong></div>
        <div className="mt-2 flex justify-between"><span>Dimension source</span><strong>{room.dimension_source === "llm_verified" ? "Drawing matched" : room.dimension_source === "drawing" ? "Drawing" : "Not available"}</strong></div>
        {room.dimension_difference_percent != null ? <div className="mt-2 flex justify-between"><span>Drawing difference</span><strong>{room.dimension_difference_percent.toFixed(2)}%</strong></div> : null}
      </div>

      <RoomGeometryStatus room={room} />
      <div className="rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-600">
        <div className="flex justify-between"><span>Room model</span><strong>{room.model_polygon?.points?.length ? "Detected" : "Not available"}</strong></div>
        <div className="mt-2 flex justify-between"><span>Wall correction</span><strong>{["wall_cell", "wall_only", "wall_geometry", "model_seed_wall_region", "model_seed_wall_faces", "wall_corrected", "vector_wall_faces"].includes(room.boundary_source) ? "Applied" : "Pending"}</strong></div>
        <div className="mt-2 flex justify-between"><span>Boundary points</span><strong>{room.point_count ?? room.display_polygon?.points?.length ?? room.geometry.points.length}</strong></div>
        <div className="mt-2 flex justify-between"><span>Stage</span><strong className="capitalize">{room.processing_stage?.replaceAll("_", " ") || "Check"}</strong></div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <Button variant="secondary" disabled={!room.model_polygon?.points?.length || room.excluded} onClick={() => void onResetToModel()}>Use model result</Button>
          <Button variant="secondary" disabled={room.boundary_source === "model_only" || room.excluded} onClick={() => void onResetToCorrected()}>Use corrected</Button>
        </div>
      </div>
      {room.validation_details?.issues?.length ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
          {room.validation_details.issues.map((issue) => <div key={issue}>• {issue}</div>)}
        </div>
      ) : null}
      {room.interpretation_status === "processing" ? (
        <div className="rounded-xl border border-violet-200 bg-violet-50 p-3 text-xs text-violet-800">
          Room details are being interpreted in the background. The saved boundary remains usable.
        </div>
      ) : null}
      {room.interpretation_warnings?.length ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
          {room.interpretation_warnings.map((warning) => <div key={warning}>• {warning}</div>)}
        </div>
      ) : null}

      <Button className="w-full" disabled={saving || room.excluded} onClick={() => void onSave(draft)}>Save details</Button>
      <div className="grid grid-cols-2 gap-2">
        <Button variant="secondary" disabled={room.excluded} onClick={onEdit}>Edit shape</Button>
        <Button className="w-full" disabled={room.excluded || room.status === "confirmed" || room.measurement_status !== "correct"} onClick={() => void onConfirm()}>Confirm</Button>
      </div>

      {!room.excluded ? (
        <details className="border-t border-slate-200 pt-4">
          <summary className="cursor-pointer text-sm font-semibold text-slate-700">Advanced geometry</summary>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <Button variant="secondary" disabled={room.is_finish_zone} onClick={onSplitLine}>Split by line</Button>
            <Button variant="secondary" disabled={room.is_finish_zone} onClick={onAddCutout}>Cutout / void</Button>
            <Button variant="secondary" disabled={room.is_finish_zone} onClick={onAddZone}>Finish zone</Button>
          </div>
          <div className="mt-3 flex gap-2">
            <select className="input min-w-0 flex-1" value={mergeId} onChange={(event) => setMergeId(event.target.value)}>
              <option value="">Merge with</option>
              {rooms.filter((item) => item.id !== room.id && !item.excluded && !item.is_finish_zone).map((item) => <option key={item.id} value={item.id}>{item.friendly_number} {item.name || ""}</option>)}
            </select>
            <Button variant="secondary" disabled={!mergeId} onClick={() => void onMerge(mergeId)}>Merge</Button>
          </div>
        </details>
      ) : null}

      {room.cutouts?.length ? (
        <details className="border-t border-slate-200 pt-4">
          <summary className="cursor-pointer text-sm font-semibold text-slate-700">Cutouts ({room.cutouts.length})</summary>
          <div className="mt-3 space-y-2">
            {room.cutouts.map((cutout, index) => (
              <div key={cutout.id} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-xs">
                <span>{cutout.name || `Cutout ${index + 1}`}</span>
                <button className="font-semibold text-red-600" onClick={() => void onDeleteCutout(cutout.id)}>Remove</button>
              </div>
            ))}
          </div>
        </details>
      ) : null}

      <details className="border-t border-slate-200 pt-4">
        <summary className="cursor-pointer text-sm font-semibold text-slate-700">Edit history</summary>
        <div className="mt-3"><RoomEditHistory items={revisions} onRestore={(id) => void onRestoreRevision(id)} /></div>
      </details>

      <div className="border-t border-slate-200 pt-4">
        {room.excluded ? <Button variant="secondary" className="w-full" onClick={() => void onRestore()}>Restore</Button> : <Button variant="secondary" className="w-full" onClick={() => void onExclude()}>Exclude</Button>}
        <button type="button" className="mt-3 w-full text-center text-xs font-medium text-slate-400 hover:text-red-600" onClick={() => void onDelete()}>Delete permanently</button>
      </div>
    </div>
  );
}
