"use client";

import type { BoqConditionOperator, BoqConditionValueType, BoqTemplateCondition } from "../types";

const NUMERIC_OPERATORS: Array<[BoqConditionOperator, string]> = [
  ["<", "Less than"], ["<=", "Less or equal"], [">", "Greater than"], [">=", "Greater or equal"], ["=", "Equal"], ["!=", "Not equal"],
];
const STRING_OPERATORS: Array<[BoqConditionOperator, string]> = [["=", "Equal"], ["!=", "Not equal"]];
const COMMON_VARIABLES = ["Width", "Height", "Length", "Thickness", "Material", "WallType", "Type_Code", "Floor", "Level", "Fire_Rating", "Glass_Type", "Finish"];

export function ConditionRow({ value, onChange, onRemove }: { value: BoqTemplateCondition; onChange: (value: BoqTemplateCondition) => void; onRemove: () => void }) {
  const condition = normalizeCondition(value);
  const operators = condition.value_type === "string" ? STRING_OPERATORS : NUMERIC_OPERATORS;

  function update(patch: Partial<BoqTemplateCondition>) {
    const next = { ...condition, ...patch };
    if (patch.value_type === "string" && !["=", "!=", "=="].includes(next.operator)) next.operator = "=";
    onChange(next);
  }

  return (
    <div className="grid gap-2 rounded-lg border border-slate-200 bg-white p-2 md:grid-cols-[160px_120px_150px_minmax(0,1fr)_44px]">
      <select value={condition.variable} onChange={(event) => update({ variable: event.target.value })} className="h-10 rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-blue-300">
        {COMMON_VARIABLES.map((variable) => <option key={variable} value={variable}>{variable}</option>)}
      </select>
      <select value={condition.value_type} onChange={(event) => update({ value_type: event.target.value as BoqConditionValueType })} className="h-10 rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-blue-300">
        <option value="number">Number</option><option value="string">Text</option>
      </select>
      <select value={condition.operator} onChange={(event) => update({ operator: event.target.value as BoqConditionOperator })} className="h-10 rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-blue-300">
        {operators.map(([operator, label]) => <option key={operator} value={operator}>{label}</option>)}
      </select>
      <input value={condition.value} type={condition.value_type === "number" ? "number" : "text"} onChange={(event) => update({ value: event.target.value })} className="h-10 rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-blue-300" placeholder="Value" />
      <button type="button" onClick={onRemove} className="h-10 rounded-lg border border-slate-200 text-sm font-semibold text-slate-500 hover:bg-slate-50">×</button>
    </div>
  );
}

export function normalizeCondition(value?: BoqTemplateCondition | null): BoqTemplateCondition {
  const variable = value?.variable || "Width";
  return {
    variable: COMMON_VARIABLES.includes(variable) ? variable : "Width",
    operator: value?.operator || "<",
    value: value?.value ?? "50",
    value_type: value?.value_type || "number",
  };
}
