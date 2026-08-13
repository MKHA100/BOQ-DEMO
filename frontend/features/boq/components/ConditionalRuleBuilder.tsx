"use client";

import { BranchOutputEditor, normalizeOutput } from "./BranchOutputEditor";
import { ConditionRow, normalizeCondition } from "./ConditionRow";
import type { BoqConditionalBranch, BoqConditionalBranchType, BoqConditionalRules, BoqTemplateCondition } from "../types";

function createBranch(branch_type: BoqConditionalBranchType): BoqConditionalBranch {
  return {
    id: `${branch_type}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    branch_type,
    conditions: branch_type === "else" ? [] : [normalizeCondition()],
    output: normalizeOutput(),
  };
}

export function ConditionalRuleBuilder({ value, onChange }: { value?: BoqConditionalRules; onChange: (value: BoqConditionalRules) => void }) {
  const rules = normalizeRules(value);
  function updateBranch(index: number, branch: BoqConditionalBranch) { onChange({ branches: rules.branches.map((item, itemIndex) => itemIndex === index ? branch : item) }); }
  function addElseIf() {
    const branches = [...rules.branches];
    const elseIndex = branches.findIndex((branch) => branch.branch_type === "else");
    const branch = createBranch("elseif");
    if (elseIndex >= 0) branches.splice(elseIndex, 0, branch); else branches.push(branch);
    onChange({ branches });
  }
  function addElse() { if (!rules.branches.some((branch) => branch.branch_type === "else")) onChange({ branches: [...rules.branches, createBranch("else")] }); }
  function removeBranch(index: number) { const next = rules.branches.filter((_, branchIndex) => branchIndex !== index); onChange({ branches: next.length ? next : [createBranch("if")] }); }

  return (
    <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-900">Rules</h3>
        <div className="flex gap-2">
          <button type="button" onClick={addElseIf} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Add Else If</button>
          <button type="button" onClick={addElse} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Add Else</button>
        </div>
      </div>
      {rules.branches.map((branch, index) => (
        <BranchCard key={branch.id || index} branch={branch} index={index} canRemove={rules.branches.length > 1} onChange={(nextBranch) => updateBranch(index, nextBranch)} onRemove={() => removeBranch(index)} />
      ))}
    </div>
  );
}

function BranchCard({ branch, index, canRemove, onChange, onRemove }: { branch: BoqConditionalBranch; index: number; canRemove: boolean; onChange: (value: BoqConditionalBranch) => void; onRemove: () => void }) {
  const normalized = normalizeBranch(branch, index);
  const title = normalized.branch_type === "if" ? "IF" : normalized.branch_type === "elseif" ? "ELSE IF" : "ELSE";
  function update(patch: Partial<BoqConditionalBranch>) { onChange({ ...normalized, ...patch }); }
  function updateCondition(conditionIndex: number, condition: BoqTemplateCondition) { update({ conditions: normalized.conditions.map((item, itemIndex) => itemIndex === conditionIndex ? condition : item) }); }
  function addCondition() { update({ conditions: [...normalized.conditions, normalizeCondition()] }); }
  function removeCondition(conditionIndex: number) { const next = normalized.conditions.filter((_, itemIndex) => itemIndex !== conditionIndex); update({ conditions: next.length ? next : [normalizeCondition()] }); }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">{title}</span>
        {canRemove ? <button type="button" onClick={onRemove} className="rounded-lg px-3 py-2 text-sm font-semibold text-slate-500 hover:bg-slate-50">Remove</button> : null}
      </div>
      {normalized.branch_type !== "else" ? (
        <div className="mt-4 space-y-2">
          {normalized.conditions.map((condition, conditionIndex) => <ConditionRow key={conditionIndex} value={condition} onChange={(next) => updateCondition(conditionIndex, next)} onRemove={() => removeCondition(conditionIndex)} />)}
          <button type="button" onClick={addCondition} className="rounded-lg border border-dashed border-slate-300 px-3 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50">Add condition</button>
        </div>
      ) : null}
      <div className="mt-4"><BranchOutputEditor value={normalized.output} onChange={(output) => update({ output })} /></div>
    </div>
  );
}

export function normalizeRules(value?: BoqConditionalRules): BoqConditionalRules {
  const branches = Array.isArray(value?.branches) && value.branches.length ? value.branches : [createBranch("if"), createBranch("else")];
  return { branches: branches.map(normalizeBranch) };
}

function normalizeBranch(value: BoqConditionalBranch, index = 0): BoqConditionalBranch {
  const branch_type: BoqConditionalBranchType = value.branch_type || (index === 0 ? "if" : "elseif");
  return {
    id: value.id || `${branch_type}-${index}`,
    branch_type,
    conditions: branch_type === "else" ? [] : value.conditions?.length ? value.conditions.map(normalizeCondition) : [normalizeCondition()],
    output: normalizeOutput(value.output),
  };
}
