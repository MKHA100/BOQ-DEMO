"use client";

import type { BoqAmountFormula, BoqFormulaOperation } from "../types";

const OPERATIONS: Array<[BoqFormulaOperation, string]> = [
  ["value", "Use one value"],
  ["multiply", "Multiply"],
  ["sum", "Add"],
  ["subtract", "Subtract"],
  ["divide", "Divide"],
  ["count", "Count"],
];

const COMMON_VARIABLES = ["Quantity", "Height", "Width", "Length", "Area", "Volume", "Thickness", "Floor"];

export function FormulaBuilder({ value, onChange }: { value?: BoqAmountFormula | Record<string, unknown> | null; onChange: (value: BoqAmountFormula) => void }) {
  const formula = normalizeFormula(value);

  function update(patch: Partial<BoqAmountFormula>) {
    onChange({ ...formula, ...patch });
  }

  function setVariable(index: number, nextValue: string) {
    const variables = [...formula.variables];
    variables[index] = nextValue;
    update({ variables });
  }

  function addVariable() {
    update({ variables: [...formula.variables, "Height"] });
  }

  function removeVariable(index: number) {
    update({ variables: formula.variables.filter((_, variableIndex) => variableIndex !== index) });
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div className="grid gap-3 sm:grid-cols-[180px_minmax(0,1fr)_120px]">
        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Formula</span>
          <select
            value={formula.operation}
            onChange={(event) => update({ operation: event.target.value as BoqFormulaOperation })}
            className="mt-2 h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm outline-none focus:border-blue-300"
          >
            {OPERATIONS.map(([operation, label]) => <option key={operation} value={operation}>{label}</option>)}
          </select>
        </label>

        <div>
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Values</span>
          <div className="mt-2 flex flex-wrap gap-2">
            {formula.operation !== "count" ? formula.variables.map((variable, index) => (
              <div key={`${variable}-${index}`} className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1">
                <select
                  value={variable}
                  onChange={(event) => setVariable(index, event.target.value)}
                  className="h-8 w-32 border-0 bg-transparent text-sm outline-none"
                >
                  {COMMON_VARIABLES.map((option) => <option key={option} value={option}>{option}</option>)}
                </select>
                <button type="button" onClick={() => removeVariable(index)} className="rounded px-2 text-xs font-semibold text-slate-500 hover:bg-slate-100">×</button>
              </div>
            )) : <span className="text-sm text-slate-500">Uses one item unless a constant is entered.</span>}
            {formula.operation !== "count" ? (
              <button type="button" onClick={addVariable} className="h-10 rounded-lg border border-dashed border-slate-300 px-3 text-sm font-semibold text-slate-600 hover:bg-white">Add value</button>
            ) : null}
          </div>
        </div>

        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Constant</span>
          <input
            value={formula.constant ?? ""}
            type="number"
            step="any"
            onChange={(event) => update({ constant: event.target.value === "" ? null : Number(event.target.value) })}
            className="mt-2 h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm outline-none focus:border-blue-300"
          />
        </label>
      </div>
    </div>
  );
}

export function normalizeFormula(value?: BoqAmountFormula | Record<string, unknown> | null): BoqAmountFormula {
  const record = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const operation = OPERATIONS.some(([item]) => item === record.operation) ? record.operation as BoqFormulaOperation : "value";
  const rawVariables = Array.isArray(record.variables) ? record.variables.map(String) : ["Quantity"];
  const variables = rawVariables.length ? rawVariables.map((variable) => COMMON_VARIABLES.includes(variable) ? variable : "Quantity") : ["Quantity"];
  const constant = typeof record.constant === "number" ? record.constant : record.constant == null || record.constant === "" ? null : Number(record.constant);
  return { operation, variables, constant: Number.isFinite(constant as number) ? constant : null };
}
