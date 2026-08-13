import type { BoqRow } from "../types";

export function BoqSourceItems({ row }: { row: BoqRow }) {
  if (row.manual) return <span className="text-xs text-slate-500">Manual item</span>;
  return (
    <div>
      <div className="flex flex-wrap gap-1.5">
        {row.source_items.slice(0, 8).map((item) => (
          <span key={item.id} title={`${item.floor || ""}${item.type_code ? ` · ${item.type_code}` : ""}`} className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-700">
            {item.display_number || item.type_code || "Source"}
          </span>
        ))}
        {row.source_items.length > 8 ? <span className="px-1 py-1 text-xs text-slate-500">+{row.source_items.length - 8}</span> : null}
      </div>
      {row.floor_names.length ? <p className="mt-2 text-xs text-slate-500">{row.floor_names.join(", ")}</p> : null}
    </div>
  );
}
