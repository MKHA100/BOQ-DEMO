"use client";

import { useEffect, useState } from "react";
import type { BoqRow } from "../types";
import { BoqSourceItems } from "./BoqSourceItems";

function statusTone(status: string): string {
  return status === "ready" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-amber-200 bg-amber-50 text-amber-700";
}

export function BoqRowEditor({ row, disabled, showRates, showAmounts, onSave }: {
  row: BoqRow; disabled: boolean; showRates: boolean; showAmounts: boolean;
  onSave: (payload: Record<string, unknown>) => Promise<void>;
}) {
  const [description, setDescription] = useState(row.description);
  const [rate, setRate] = useState(row.rate?.toString() || "");
  useEffect(() => setDescription(row.description), [row.description]);
  useEffect(() => setRate(row.rate?.toString() || ""), [row.rate]);
  return (
    <tr className={row.excluded ? "border-t border-slate-200 bg-slate-50 opacity-50" : "border-t border-slate-200 align-top hover:bg-slate-50"}>
      <td className="px-4 py-3 font-semibold text-slate-700">{row.boq_item_number || row.subcategory_code || "—"}</td>
      <td className="px-4 py-3"><p>{row.section || "—"}</p><p className="mt-1 text-xs text-slate-400">{row.item_code || "No type code"}</p></td>
      <td className="min-w-[390px] px-4 py-3">
        <textarea className="min-h-14 w-full resize-y rounded-md border border-transparent bg-transparent px-2 py-1 focus:border-blue-300 focus:bg-white" value={description} onChange={(event) => setDescription(event.target.value)} onBlur={() => { if (description !== row.description) void onSave({ description }); }} disabled={disabled} />
        {row.missing_fields.length ? <p className="mt-1 text-xs text-amber-700">Missing: {row.missing_fields.map((field) => field.replaceAll("_", " ")).join(", ")}</p> : null}
      </td>
      <td className="min-w-[220px] px-4 py-3"><BoqSourceItems row={row} /></td>
      <td className="px-4 py-3 text-right font-semibold">{row.unit === "nr" ? Math.round(row.quantity) : row.quantity.toFixed(3)}</td>
      <td className="px-4 py-3">{row.unit}</td>
      {showRates ? <td className="px-4 py-3"><input className="input w-28 text-right" type="number" min="0" step="0.01" value={rate} onChange={(event) => setRate(event.target.value)} onBlur={() => { const next = rate === "" ? null : Number(rate); if (next !== row.rate) void onSave({ rate: next }); }} disabled={disabled} /></td> : null}
      {showAmounts ? <td className="px-4 py-3 text-right font-semibold">{row.amount == null ? "—" : row.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td> : null}
      <td className="px-4 py-3"><span className={`rounded-full border px-2.5 py-1 text-xs font-semibold capitalize ${statusTone(row.status)}`}>{row.status.replace("_", " ")}</span></td>
      <td className="px-4 py-3"><button className="text-xs font-semibold text-slate-600" onClick={() => void onSave({ excluded: !row.excluded })}>{row.excluded ? "Include" : "Exclude"}</button></td>
    </tr>
  );
}
