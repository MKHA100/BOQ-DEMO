"use client";

import { useEffect, useState } from "react";
import { Button } from "@/shared/components/Button";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import type { BoqDocumentSetup } from "../types";
import { BoqDrawer } from "./BoqDrawer";
import { BoqSectionOrder } from "./BoqSectionOrder";

export function BoqSettingsDrawer({
  open,
  setup,
  saving,
  error,
  onClose,
  onSave,
}: {
  open: boolean;
  setup: BoqDocumentSetup | null;
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onSave: (setup: BoqDocumentSetup) => Promise<void>;
}) {
  const [form, setForm] = useState<BoqDocumentSetup | null>(setup);
  const [advanced, setAdvanced] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (open && setup) {
      setForm(setup);
      setSaved(false);
    }
  }, [open, setup]);

  if (!form) return null;
  const update = <K extends keyof BoqDocumentSetup>(key: K, value: BoqDocumentSetup[K]) => {
    setSaved(false);
    setForm((current) => current ? { ...current, [key]: value } : current);
  };

  return (
    <BoqDrawer
      open={open}
      title="BOQ settings"
      subtitle="Project details and the most commonly used PDF and Excel options."
      onClose={onClose}
    >
      <div className="space-y-6 p-6">
        <section>
          <h3 className="text-sm font-semibold text-slate-900">Project details</h3>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <TextField label="Project name" value={form.project_name} onChange={(value) => update("project_name", value)} />
            <TextField label="BOQ title" value={form.boq_title} onChange={(value) => update("boq_title", value)} />
            <TextField label="Client" value={form.client_name} onChange={(value) => update("client_name", value)} />
            <TextField label="Consultant" value={form.consultant_name} onChange={(value) => update("consultant_name", value)} />
            <TextField label="Location" value={form.location} onChange={(value) => update("location", value)} />
            <TextField label="Currency" value={form.currency} onChange={(value) => update("currency", value)} />
          </div>
        </section>

        <section className="border-t border-slate-200 pt-5">
          <h3 className="text-sm font-semibold text-slate-900">Report options</h3>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Toggle label="Show rates" value={form.include_rates} onChange={(value) => update("include_rates", value)} />
            <Toggle label="Show amounts" value={form.include_amounts} onChange={(value) => update("include_amounts", value)} />
            <Toggle label="Include preliminaries" value={form.include_preliminaries} onChange={(value) => update("include_preliminaries", value)} />
            <Toggle label="Include signature section" value={form.include_signature_section} onChange={(value) => update("include_signature_section", value)} />
          </div>
          <label className="mt-4 block">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">VAT percentage</span>
            <input className="input mt-2 w-full" type="number" min="0" max="100" step="0.01" value={form.vat_percentage} onChange={(event) => update("vat_percentage", Number(event.target.value))} />
          </label>
        </section>

        <section className="border-t border-slate-200 pt-5">
          <button type="button" className="flex w-full items-center justify-between text-left" onClick={() => setAdvanced((value) => !value)}>
            <span>
              <span className="block text-sm font-semibold text-slate-900">Advanced settings</span>
              <span className="mt-1 block text-xs text-slate-500">Numbering, units, descriptions, provisional sums and bill order.</span>
            </span>
            <span className="text-lg text-slate-400">{advanced ? "−" : "+"}</span>
          </button>

          {advanced ? (
            <div className="mt-5 space-y-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <SelectField label="Format style" value={form.format_style} options={[
                  ["formal_tender", "Formal tender"], ["quantity_takeoff", "Quantity takeoff"], ["standard_construction", "Standard construction"], ["lot_based", "Lot based"],
                ]} onChange={(value) => update("format_style", value as BoqDocumentSetup["format_style"])} />
                <SelectField label="Item numbering" value={form.item_numbering_format} options={[
                  ["section_sequence", "Section sequence"], ["source_item_number", "Source item number"], ["simple_sequence", "Simple sequence"],
                ]} onChange={(value) => update("item_numbering_format", value as BoqDocumentSetup["item_numbering_format"])} />
                <SelectField label="Measurement units" value={form.measurement_unit_style} options={[
                  ["metric", "Metric"], ["imperial", "Imperial"], ["mixed", "Mixed"],
                ]} onChange={(value) => update("measurement_unit_style", value as BoqDocumentSetup["measurement_unit_style"])} />
                <SelectField label="Description style" value={form.description_style} options={[
                  ["standard", "Standard"], ["detailed", "Detailed"], ["short", "Short"],
                ]} onChange={(value) => update("description_style", value as BoqDocumentSetup["description_style"])} />
              </div>
              <Toggle label="Include provisional sums" value={form.include_provisional_sums} onChange={(value) => update("include_provisional_sums", value)} />
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Bill order</p>
                <div className="mt-3"><BoqSectionOrder value={form.section_order.length ? form.section_order : ["1", "2", "3", "4", "5", "6", "7", "8", "9"]} onChange={(value) => update("section_order", value)} /></div>
              </div>
            </div>
          ) : null}
        </section>

        {error ? <ErrorMessage message={error} /> : null}
        {saved ? <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">Settings saved. The BOQ will refresh in the background.</div> : null}
      </div>
      <footer className="sticky bottom-0 flex justify-end gap-2 border-t border-slate-200 bg-white px-6 py-4">
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button disabled={saving} onClick={() => void onSave(form).then(() => setSaved(true))}>{saving ? "Saving…" : "Save settings"}</Button>
      </footer>
    </BoqDrawer>
  );
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label><span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span><input className="input mt-2 w-full" value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

function SelectField({ label, value, options, onChange }: { label: string; value: string; options: Array<[string, string]>; onChange: (value: string) => void }) {
  return <label><span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span><select className="input mt-2 w-full" value={value} onChange={(event) => onChange(event.target.value)}>{options.map(([optionValue, optionLabel]) => <option key={optionValue} value={optionValue}>{optionLabel}</option>)}</select></label>;
}

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (value: boolean) => void }) {
  return <label className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm font-medium text-slate-700"><span>{label}</span><input type="checkbox" checked={value} onChange={(event) => onChange(event.target.checked)} /></label>;
}
