"use client";

import { Button } from "@/shared/components/Button";

export function BoqExportOptions({ floors, floorId, mode, disabled, onFloorChange, onModeChange, onExport }: {
  floors: Array<{ id: string; name: string }>;
  floorId: string | null;
  mode: "combined" | "floor_breakdown" | "selected_floor";
  disabled: boolean;
  onFloorChange: (value: string | null) => void;
  onModeChange: (value: "combined" | "floor_breakdown" | "selected_floor") => void;
  onExport: (format: "pdf" | "xlsx" | "csv") => void;
}) {
  return <section className="rounded-2xl border border-slate-200 bg-white p-5"><h3 className="font-semibold">Create export</h3><p className="mt-1 text-sm text-slate-500">Exports use the saved formal report, selected template version, document setup, source traceability, and Needs Review appendix.</p><div className="mt-5 grid gap-4 md:grid-cols-2"><label><span className="text-xs font-semibold uppercase text-slate-500">Export layout</span><select className="input mt-2 w-full" value={mode} onChange={(event) => onModeChange(event.target.value as typeof mode)}><option value="combined">Combined project</option><option value="floor_breakdown">Floor breakdown</option><option value="selected_floor">Selected floor only</option></select></label>{mode === "selected_floor" ? <label><span className="text-xs font-semibold uppercase text-slate-500">Floor</span><select className="input mt-2 w-full" value={floorId || ""} onChange={(event) => onFloorChange(event.target.value || null)}><option value="">Select floor</option>{floors.map((floor) => <option key={floor.id} value={floor.id}>{floor.name}</option>)}</select></label> : null}</div><div className="mt-5 flex flex-wrap gap-2"><Button disabled={disabled || (mode === "selected_floor" && !floorId)} onClick={() => onExport("pdf")}>Generate PDF</Button><Button variant="secondary" disabled={disabled || (mode === "selected_floor" && !floorId)} onClick={() => onExport("xlsx")}>Generate Excel</Button><Button variant="secondary" disabled={disabled || (mode === "selected_floor" && !floorId)} onClick={() => onExport("csv")}>Generate CSV</Button></div></section>;
}
