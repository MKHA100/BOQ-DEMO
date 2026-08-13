"use client";

import { useEffect, useState } from "react";
import { Button } from "@/shared/components/Button";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import { BoqDrawer } from "./BoqDrawer";

export type ManualBoqItemForm = {
  description: string;
  section: string;
  item_code: string;
  quantity: number;
  unit: string;
  rate: string;
};

const emptyForm: ManualBoqItemForm = {
  description: "",
  section: "Other items",
  item_code: "",
  quantity: 1,
  unit: "item",
  rate: "",
};

export function BoqManualItemDrawer({
  open,
  saving,
  error,
  onClose,
  onAdd,
}: {
  open: boolean;
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onAdd: (form: ManualBoqItemForm) => Promise<void>;
}) {
  const [form, setForm] = useState<ManualBoqItemForm>(emptyForm);
  useEffect(() => { if (open) setForm(emptyForm); }, [open]);

  return (
    <BoqDrawer open={open} title="Add manual BOQ item" subtitle="Add an item that is not linked to a detected model element." onClose={onClose}>
      <div className="space-y-4 p-6">
        <label className="block"><span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Description</span><textarea className="input mt-2 min-h-28 w-full" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Section" value={form.section} onChange={(value) => setForm({ ...form, section: value })} />
          <Field label="Item code" value={form.item_code} onChange={(value) => setForm({ ...form, item_code: value })} />
          <label><span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Quantity</span><input className="input mt-2 w-full" type="number" min="0.001" step="0.001" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: Number(event.target.value) })} /></label>
          <Field label="Unit" value={form.unit} onChange={(value) => setForm({ ...form, unit: value })} />
          <label><span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Rate</span><input className="input mt-2 w-full" type="number" min="0" step="0.01" value={form.rate} onChange={(event) => setForm({ ...form, rate: event.target.value })} /></label>
        </div>
        {error ? <ErrorMessage message={error} /> : null}
      </div>
      <footer className="sticky bottom-0 flex justify-end gap-2 border-t border-slate-200 bg-white px-6 py-4">
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button disabled={saving || !form.description.trim() || form.quantity <= 0 || !form.unit.trim()} onClick={() => void onAdd(form)}>{saving ? "Adding…" : "Add item"}</Button>
      </footer>
    </BoqDrawer>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label><span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span><input className="input mt-2 w-full" value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}
