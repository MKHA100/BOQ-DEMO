"use client";

import { useEffect, useState } from "react";
import { Button } from "@/shared/components/Button";
import type { OpeningElement, Wall, WallPatch, WallValidationWarning } from "../types";

const number = (value: number | null | undefined, digits = 2) => value == null ? "—" : value.toFixed(digits);
const warningMessage = (warning: WallValidationWarning | string) => typeof warning === "string" ? warning : warning.message;

export function WallInspector({
  wall,
  openings,
  walls,
  saving,
  onSave,
  onAssign,
  onSplit,
  onMerge,
  onRestore,
  onDelete,
}: {
  wall: Wall | null;
  openings: OpeningElement[];
  walls: Wall[];
  saving: boolean;
  onSave: (patch: WallPatch) => Promise<void>;
  onAssign: (elementId: string) => Promise<void>;
  onSplit: () => Promise<void>;
  onMerge: (wallId: string) => Promise<void>;
  onRestore: () => Promise<void>;
  onDelete: () => Promise<void>;
}) {
  const [draft, setDraft] = useState<WallPatch>({});
  const [openingId, setOpeningId] = useState("");
  const [mergeId, setMergeId] = useState("");

  useEffect(() => {
    setDraft(wall ? {
      classification: wall.classification || undefined,
      wall_type: wall.wall_type,
      thickness_mm: wall.thickness_mm,
      height_override_mm: wall.height_override_mm,
      side_1_finish: wall.side_1_finish,
      side_2_finish: wall.side_2_finish,
    } : {});
    setOpeningId("");
    setMergeId("");
  }, [wall]);

  if (!wall) {
    return <div className="p-6 text-sm text-slate-500">Select a wall to review its measurements, openings and validation.</div>;
  }

  const warnings = (wall.validation_warnings || []).filter(
    (warning) => typeof warning !== "string" && warning.severity === "error",
  );
  const confidence = wall.confidence == null
    ? null
    : wall.confidence <= 1 ? wall.confidence * 100 : wall.confidence;

  return (
    <div className="space-y-5 p-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Selected wall</p>
        <div className="mt-1 flex items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-slate-950">{wall.display_number}</h3>
            <p className="mt-1 text-xs capitalize text-slate-500">
              {wall.user_confirmed ? "User approved" : wall.status === "confirmed" ? "System verified" : wall.status.replaceAll("_", " ")}
            </p>
          </div>
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-semibold capitalize text-slate-600">
            {wall.source || (wall.source_element_id ? "model" : "manual")}
          </span>
        </div>
        {confidence != null ? <p className="mt-2 text-xs text-slate-500">Detection confidence {number(confidence, 0)}%</p> : null}
      </div>

      {warnings.length ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-800">Needs attention</p>
          <ul className="mt-2 space-y-1.5 text-xs text-amber-900">
            {warnings.map((warning, index) => <li key={`${warningMessage(warning)}-${index}`}>• {warningMessage(warning)}</li>)}
          </ul>
        </div>
      ) : (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-800">Geometry checked automatically.</div>
      )}

      <label className="block text-sm font-medium">
        Classification
        <select className="input mt-1 w-full" value={draft.classification || ""} onChange={(event) => setDraft({ ...draft, classification: event.target.value as "internal" | "external" })}>
          <option value="">Select</option>
          <option value="external">External</option>
          <option value="internal">Internal</option>
        </select>
      </label>
      <div className="grid grid-cols-2 gap-3">
        <label className="block text-sm font-medium">
          Wall type
          <input className="input mt-1 w-full" value={draft.wall_type || ""} onChange={(event) => setDraft({ ...draft, wall_type: event.target.value })} />
        </label>
        <label className="block text-sm font-medium">
          Thickness (mm)
          <input className="input mt-1 w-full" type="number" value={draft.thickness_mm ?? ""} onChange={(event) => setDraft({ ...draft, thickness_mm: event.target.value ? Number(event.target.value) : null })} />
        </label>
      </div>
      <label className="block text-sm font-medium">
        Height override (mm)
        <input className="input mt-1 w-full" type="number" value={draft.height_override_mm ?? ""} onChange={(event) => setDraft({ ...draft, height_override_mm: event.target.value ? Number(event.target.value) : null, use_floor_height: !event.target.value })} />
      </label>
      <div className="grid grid-cols-2 gap-3">
        <label className="block text-sm font-medium">
          Side 1 finish
          <input className="input mt-1 w-full" value={draft.side_1_finish || ""} onChange={(event) => setDraft({ ...draft, side_1_finish: event.target.value })} />
        </label>
        <label className="block text-sm font-medium">
          Side 2 finish
          <input className="input mt-1 w-full" value={draft.side_2_finish || ""} onChange={(event) => setDraft({ ...draft, side_2_finish: event.target.value })} />
        </label>
      </div>

      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
        <div className="flex justify-between"><span>Length</span><strong>{number(wall.length_mm ? wall.length_mm / 1000 : null)} m</strong></div>
        <div className="mt-2 flex justify-between"><span>Height</span><strong>{number(wall.height_mm ? wall.height_mm / 1000 : null)} m</strong></div>
        <div className="mt-2 flex justify-between"><span>Thickness</span><strong>{number(wall.thickness_mm, 0)} mm</strong></div>
        <div className="mt-2 flex justify-between"><span>Gross area</span><strong>{number(wall.gross_area_m2)} m²</strong></div>
        <div className="mt-2 flex justify-between"><span>Deduction</span><strong>{number(wall.deduction_area_m2)} m²</strong></div>
        <div className="mt-2 flex justify-between border-t border-slate-200 pt-2"><span>Net area</span><strong>{number(wall.net_area_m2)} m²</strong></div>
      </div>
      <Button className="w-full" disabled={saving} onClick={() => void onSave(draft)}>Save wall</Button>

      <div className="border-t border-slate-200 pt-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold">Connected openings</p>
          <span className="text-xs text-slate-500">{wall.openings.length}</span>
        </div>
        <div className="mt-2 space-y-1">
          {wall.openings.length ? wall.openings.map((item) => (
            <div key={item.id} className="flex justify-between rounded-lg bg-slate-50 px-3 py-2 text-xs">
              <span>{item.element_display_number || item.element_number || item.element_type}</span>
              <span>{number(item.deduction_area_m2)} m²</span>
            </div>
          )) : <p className="text-xs text-slate-500">No openings assigned.</p>}
        </div>
        <div className="mt-3 flex gap-2">
          <select className="input min-w-0 flex-1" value={openingId} onChange={(event) => setOpeningId(event.target.value)}>
            <option value="">Select opening</option>
            {openings.map((item) => <option key={item.id} value={item.id}>{item.display_number}{item.type_code ? ` · ${item.type_code}` : ""}</option>)}
          </select>
          <Button variant="secondary" disabled={!openingId || saving} onClick={() => void onAssign(openingId)}>Assign</Button>
        </div>
      </div>

      <div className="border-t border-slate-200 pt-4">
        <div className="flex gap-2">
          <Button variant="secondary" disabled={saving} onClick={() => void onSplit()}>Split</Button>
          <Button variant="secondary" disabled={saving || wall.source === "manual"} onClick={() => void onRestore()}>Restore line</Button>
        </div>
        <div className="mt-3 flex gap-2">
          <select className="input min-w-0 flex-1" value={mergeId} onChange={(event) => setMergeId(event.target.value)}>
            <option value="">Merge with</option>
            {walls.filter((item) => item.id !== wall.id).map((item) => <option key={item.id} value={item.id}>{item.display_number}</option>)}
          </select>
          <Button variant="secondary" disabled={!mergeId || saving} onClick={() => void onMerge(mergeId)}>Merge</Button>
        </div>
      </div>

      <div className="border-t border-slate-200 pt-4">
        <Button
          className="w-full"
          variant="danger"
          disabled={saving}
          onClick={() => {
            if (window.confirm(`Delete ${wall.display_number}? This wall will stay suppressed when generated walls are refreshed.`)) {
              void onDelete();
            }
          }}
        >
          Delete wall
        </Button>
      </div>
    </div>
  );
}
