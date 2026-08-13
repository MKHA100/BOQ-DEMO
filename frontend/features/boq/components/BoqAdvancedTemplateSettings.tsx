"use client";

import type { BoqPlaceholder, BoqTemplateItem } from "../types";
import { ConditionalRuleBuilder, normalizeRules } from "./ConditionalRuleBuilder";
import { FormulaBuilder, normalizeFormula } from "./FormulaBuilder";

export function BoqAdvancedTemplateSettings({
  value,
  placeholders: _placeholders,
  onChange,
}: {
  value: Omit<BoqTemplateItem, "id" | "template_id">;
  placeholders: BoqPlaceholder[];
  onChange: (value: Omit<BoqTemplateItem, "id" | "template_id">) => void;
}) {
  const branchRules = !Array.isArray(value.conditional_rules) && value.conditional_rules?.branches
    ? normalizeRules(value.conditional_rules)
    : normalizeRules();
  return (
    <div className="space-y-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <label><span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Keywords</span><input className="input mt-2 w-full" value={value.keywords.join(", ")} onChange={(event) => onChange({ ...value, keywords: event.target.value.split(",").map((item) => item.trim()).filter(Boolean) })} /></label>
        <label><span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Sort order</span><input className="input mt-2 w-full" type="number" value={value.sort_order} onChange={(event) => onChange({ ...value, sort_order: Number(event.target.value) })} /></label>
      </div>
      <label className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700"><span>Use conditional description rules</span><input type="checkbox" checked={value.template_mode === "conditional"} onChange={(event) => onChange({ ...value, template_mode: event.target.checked ? "conditional" : "standard", conditional_rules: event.target.checked ? branchRules : [] })} /></label>
      {value.template_mode === "conditional" ? <ConditionalRuleBuilder value={branchRules} onChange={(conditional_rules) => onChange({ ...value, conditional_rules })} /> : null}
      <label className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700"><span>Template item is active</span><input type="checkbox" checked={value.is_active} onChange={(event) => onChange({ ...value, is_active: event.target.checked })} /></label>
      <FormulaBuilder value={normalizeFormula(value.formula)} onChange={(formula) => onChange({ ...value, formula })} />
    </div>
  );
}
