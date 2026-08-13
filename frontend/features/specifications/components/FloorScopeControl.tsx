"use client";

import type { ChangeEvent } from "react";
import type { FloorOption, ScopeMode } from "../types";

export function FloorScopeControl({
  floors,
  scopeMode,
  floorIds,
  disabled,
  onChange,
}: {
  floors: FloorOption[];
  scopeMode: ScopeMode;
  floorIds: string[];
  disabled?: boolean;
  onChange: (scopeMode: ScopeMode, floorIds: string[]) => void;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Applies to</label>
        <select
          value={scopeMode}
          disabled={disabled}
          onChange={(event: ChangeEvent<HTMLSelectElement>) => {
            const next = event.target.value as ScopeMode;
            onChange(next, next === "all" ? [] : floorIds.length ? floorIds : floors[0] ? [floors[0].id] : []);
          }}
          className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none focus:border-blue-400"
        >
          <option value="all">All floors</option>
          <option value="selected">Selected floors</option>
        </select>
      </div>
      {scopeMode === "selected" ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {floors.map((floor) => {
            const selected = floorIds.includes(floor.id);
            return (
              <label
                key={floor.id}
                className={`inline-flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm ${selected ? "border-blue-200 bg-blue-50 text-blue-700" : "border-slate-200 bg-white text-slate-600"}`}
              >
                <input
                  type="checkbox"
                  checked={selected}
                  disabled={disabled}
                  onChange={(event: ChangeEvent<HTMLInputElement>) => {
                    const next = event.target.checked
                      ? [...floorIds, floor.id]
                      : floorIds.filter((id) => id !== floor.id);
                    if (next.length) onChange("selected", next);
                  }}
                />
                {floor.name}
              </label>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
