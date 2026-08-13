"use client";

import { useMemo, useState } from "react";
import type { ReviewElement } from "../types";

const typeLabel = { door: "Door", window: "Window", wall: "Wall" } as const;
const typeTone = {
  door: "border-blue-200 bg-blue-50 text-blue-700",
  window: "border-teal-200 bg-teal-50 text-teal-700",
  wall: "border-violet-200 bg-violet-50 text-violet-700",
} as const;

export function ElementList({ elements, selectedId, onSelect }: {
  elements: ReviewElement[];
  selectedId: string | null;
  onSelect: (element: ReviewElement) => void;
}) {
  const [search, setSearch] = useState("");
  const results = useMemo(() => {
    const term = search.trim().toLowerCase();
    return [...elements]
      .sort((a, b) => a.item_number - b.item_number)
      .filter((element) => {
        if (!term) return true;
        return [element.display_number, element.item_number, element.type_code, element.tag_text, element.element_type]
          .some((value) => String(value || "").toLowerCase().includes(term));
      });
  }, [elements, search]);

  return (
    <section className="flex min-h-0 flex-1 flex-col border-t border-slate-200 pt-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Items</p>
        <span className="text-xs font-medium text-slate-500">{results.length}</span>
      </div>
      <input
        className="input h-9 text-sm"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Find item or tag"
        aria-label="Find item or tag"
      />
      <div className="mt-3 min-h-0 flex-1 space-y-1 overflow-y-auto pr-1">
        {results.map((element) => {
          const selected = element.id === selectedId;
          const code = String(element.resolved_data?.type_code || element.type_code || element.tag_text || "No type");
          return (
            <button
              key={element.id}
              type="button"
              onClick={() => onSelect(element)}
              className={selected
                ? "w-full rounded-lg border border-blue-300 bg-blue-50 px-3 py-2 text-left shadow-sm"
                : "w-full rounded-lg border border-transparent px-3 py-2 text-left hover:border-slate-200 hover:bg-slate-50"}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-semibold text-slate-900">{element.display_number}</span>
                <span className={`rounded-md border px-1.5 py-0.5 text-[10px] font-semibold ${typeTone[element.element_type]}`}>
                  {typeLabel[element.element_type]}
                </span>
              </div>
              <div className="mt-1 flex items-center justify-between gap-2 text-xs text-slate-500">
                <span className="truncate font-medium">{code}</span>
                <span className={element.status === "needs_review" ? "text-amber-700" : element.status === "confirmed" ? "text-emerald-700" : "text-slate-500"}>
                  {element.status === "confirmed" && !element.user_confirmed ? "system checked" : element.status.replace("_", " ")}
                </span>
              </div>
              {element.element_type !== "wall" ? (
                <p className="mt-1 truncate text-[11px] text-slate-400">
                  {element.resolved_data?.width_mm && element.resolved_data?.height_mm
                    ? `${String(element.resolved_data.width_mm)} × ${String(element.resolved_data.height_mm)} mm`
                    : "Size will use scale or schedule"}
                </p>
              ) : null}
            </button>
          );
        })}
        {!results.length ? <p className="rounded-lg bg-slate-50 px-3 py-4 text-center text-xs text-slate-500">No matching items.</p> : null}
      </div>
    </section>
  );
}
