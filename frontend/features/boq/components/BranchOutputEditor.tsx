"use client";

import { FormulaBuilder, normalizeFormula } from "./FormulaBuilder";
import type { BoqConditionalBranchOutput } from "../types";

const UNIT_OPTIONS = ["m²", "m2", "m", "m3", "nr", "pcs", "Item", "No"];

export function BranchOutputEditor({ value, onChange }: { value: BoqConditionalBranchOutput; onChange: (value: BoqConditionalBranchOutput) => void }) {
  const output = normalizeOutput(value);
  function update(patch: Partial<BoqConditionalBranchOutput>) { onChange({ ...output, ...patch }); }

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-3">
      <label className="block">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Description</span>
        <textarea value={output.description_template} onChange={(event) => update({ description_template: event.target.value })} className="mt-2 min-h-[84px] w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-300" />
      </label>
      <div className="grid gap-3 lg:grid-cols-[180px_minmax(0,1fr)]">
        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Unit</span>
          <input list="template-unit-options" value={output.unit} onChange={(event) => update({ unit: event.target.value })} className="mt-2 h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm outline-none focus:border-blue-300" />
          <datalist id="template-unit-options">{UNIT_OPTIONS.map((unit) => <option key={unit} value={unit} />)}</datalist>
        </label>
        <FormulaBuilder value={output.amount_formula} onChange={(amount_formula) => update({ amount_formula })} />
      </div>
    </div>
  );
}

export function normalizeOutput(value?: BoqConditionalBranchOutput | null): BoqConditionalBranchOutput {
  return {
    description_template: value?.description_template || "[HEIGHT] × [WIDTH] item",
    unit: value?.unit || "m²",
    amount_formula: normalizeFormula(value?.amount_formula),
  };
}
