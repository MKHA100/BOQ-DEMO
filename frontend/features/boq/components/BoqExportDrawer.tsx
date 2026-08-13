"use client";

import { useState } from "react";
import { Button } from "@/shared/components/Button";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import type { BoqExport } from "../types";
import { BoqDrawer } from "./BoqDrawer";
import { BoqExportHistory } from "./BoqExportHistory";

export type BoqExportMode = "combined" | "floor_breakdown" | "selected_floor";

export function BoqExportDrawer({
  open,
  floors,
  exports,
  stale,
  saving,
  error,
  initialMode = "combined",
  onClose,
  onCreate,
  onDownload,
}: {
  open: boolean;
  floors: Array<{ id: string; name: string }>;
  exports: BoqExport[];
  stale: boolean;
  saving: boolean;
  error: string | null;
  initialMode?: BoqExportMode;
  onClose: () => void;
  onCreate: (format: "pdf" | "xlsx" | "csv", mode: BoqExportMode, floorId: string | null) => Promise<void>;
  onDownload: (item: BoqExport) => Promise<void>;
}) {
  const [mode, setMode] = useState<BoqExportMode>(initialMode);
  const [floorId, setFloorId] = useState<string | null>(null);
  const disabled = saving || stale || (mode === "selected_floor" && !floorId);

  return (
    <BoqDrawer open={open} title="Download BOQ" width="max-w-3xl" onClose={onClose}>
      <div className="space-y-6 p-6">
        <section className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <label>
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Layout</span>
              <select className="input mt-2 w-full" value={mode} onChange={(event) => setMode(event.target.value as BoqExportMode)}>
                <option value="combined">Combined project</option>
                <option value="floor_breakdown">Floor breakdown</option>
                <option value="selected_floor">Selected floor only</option>
              </select>
            </label>
            {mode === "selected_floor" ? (
              <label>
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Floor</span>
                <select className="input mt-2 w-full" value={floorId || ""} onChange={(event) => setFloorId(event.target.value || null)}>
                  <option value="">Select floor</option>
                  {floors.map((floor) => <option key={floor.id} value={floor.id}>{floor.name}</option>)}
                </select>
              </label>
            ) : null}
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            <Button disabled={disabled} onClick={() => void onCreate("pdf", mode, floorId)}>PDF</Button>
            <Button variant="secondary" disabled={disabled} onClick={() => void onCreate("xlsx", mode, floorId)}>Excel</Button>
            <Button variant="secondary" disabled={disabled} onClick={() => void onCreate("csv", mode, floorId)}>CSV</Button>
          </div>
          {stale ? <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">Refresh the BOQ before downloading.</p> : null}
        </section>

        {error ? <ErrorMessage message={error} /> : null}
        <BoqExportHistory exports={exports} onDownload={(item) => void onDownload(item)} />
      </div>
    </BoqDrawer>
  );
}
