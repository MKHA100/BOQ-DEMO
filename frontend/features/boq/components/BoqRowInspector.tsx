"use client";

import { useEffect, useState } from "react";
import { Button } from "@/shared/components/Button";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import type { BoqRow } from "../types";
import { BoqDrawer } from "./BoqDrawer";
import { BoqSourceItems } from "./BoqSourceItems";

export function BoqRowInspector({
  row,
  open,
  saving,
  error,
  showRates,
  showAmounts,
  onClose,
  onSave,
}: {
  row: BoqRow | null;
  open: boolean;
  saving: boolean;
  error: string | null;
  showRates: boolean;
  showAmounts: boolean;
  onClose: () => void;
  onSave: (payload: Record<string, unknown>) => Promise<void>;
}) {
  const [description, setDescription] = useState("");
  const [section, setSection] = useState("");
  const [itemCode, setItemCode] = useState("");
  const [quantity, setQuantity] = useState(0);
  const [unit, setUnit] = useState("");
  const [rate, setRate] = useState("");
  const [status, setStatus] = useState<"ready" | "needs_review">("ready");
  const [excluded, setExcluded] = useState(false);

  useEffect(() => {
    if (!row) return;
    setDescription(row.description);
    setSection(row.section || "");
    setItemCode(row.item_code || "");
    setQuantity(row.quantity);
    setUnit(row.unit);
    setRate(row.rate == null ? "" : String(row.rate));
    setStatus(row.status === "ready" ? "ready" : "needs_review");
    setExcluded(row.excluded);
  }, [row]);

  if (!row) return null;

  return (
    <BoqDrawer
      open={open}
      title={row.boq_item_number ? `Edit ${row.boq_item_number}` : "Edit BOQ item"}
      subtitle="Changes are saved to the current BOQ row. Canonical measured quantities remain traceable through the source items below."
      onClose={onClose}
    >
      <div className="space-y-6 p-6">
        <section className="space-y-4">
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Description</span>
            <textarea className="input mt-2 min-h-32 w-full" value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Section" value={section} onChange={setSection} />
            <Field label="Item code" value={itemCode} onChange={setItemCode} />
            <label>
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Quantity</span>
              <input className="input mt-2 w-full" type="number" min="0" step="0.001" value={quantity} onChange={(event) => setQuantity(Number(event.target.value))} disabled={!row.manual} />
              {!row.manual ? <span className="mt-1 block text-xs text-slate-400">Measured from canonical source items.</span> : null}
            </label>
            <Field label="Unit" value={unit} onChange={setUnit} />
            {showRates ? (
              <label>
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Rate</span>
                <input className="input mt-2 w-full" type="number" min="0" step="0.01" value={rate} onChange={(event) => setRate(event.target.value)} />
              </label>
            ) : null}
            <label>
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Status</span>
              <select className="input mt-2 w-full" value={status} onChange={(event) => setStatus(event.target.value as typeof status)}>
                <option value="ready">Ready</option>
                <option value="needs_review">Needs Review</option>
              </select>
            </label>
          </div>
          {showAmounts ? (
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Amount</p>
              <p className="mt-1 text-lg font-semibold text-slate-900">{row.amount == null ? "—" : row.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
            </div>
          ) : null}
          <label className="flex items-center justify-between rounded-xl border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700">
            <span>Exclude this item from the report</span>
            <input type="checkbox" checked={excluded} onChange={(event) => setExcluded(event.target.checked)} />
          </label>
          {row.missing_fields.length ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              Missing: {row.missing_fields.map((field) => field.replaceAll("_", " ")).join(", ")}
            </div>
          ) : null}
        </section>

        <section className="border-t border-slate-200 pt-5">
          <h3 className="text-sm font-semibold text-slate-900">Source items</h3>
          <p className="mt-1 text-xs text-slate-500">Permanent item numbers and floor references used to create this BOQ row.</p>
          <div className="mt-3"><BoqSourceItems row={row} /></div>
        </section>
        {error ? <ErrorMessage message={error} /> : null}
      </div>
      <footer className="sticky bottom-0 flex justify-end gap-2 border-t border-slate-200 bg-white px-6 py-4">
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button disabled={saving || !description.trim() || !unit.trim() || quantity < 0} onClick={() => void onSave({
          description: description.trim(),
          section: section.trim() || null,
          item_code: itemCode.trim() || null,
          ...(row.manual ? { quantity } : {}),
          unit: unit.trim(),
          rate: rate === "" ? null : Number(rate),
          status,
          excluded,
        })}>{saving ? "Saving…" : "Save item"}</Button>
      </footer>
    </BoqDrawer>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label><span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span><input className="input mt-2 w-full" value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}
