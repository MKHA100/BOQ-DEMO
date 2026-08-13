import type { BoqRow } from "../types";

function quantityLabel(row: BoqRow): string {
  if (["nr", "no", "nos", "each", "ea", "item"].includes(row.unit.toLowerCase())) return String(Math.round(row.quantity));
  return row.quantity.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}

function statusTone(status: string): string {
  return status === "ready" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700";
}

export function BoqReportTable({
  rows,
  selectedRowId,
  showRates,
  showAmounts,
  onSelect,
}: {
  rows: BoqRow[];
  selectedRowId: string | null;
  showRates: boolean;
  showAmounts: boolean;
  onSelect: (row: BoqRow) => void;
}) {
  return (
    <div className="max-h-[700px] overflow-auto">
      <table className="w-full border-collapse text-left text-sm">
        <thead className="sticky top-0 z-10 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Item</th>
            <th className="px-4 py-3">Description</th>
            <th className="px-4 py-3">Unit</th>
            <th className="px-4 py-3 text-right">Quantity</th>
            {showRates ? <th className="px-4 py-3 text-right">Rate</th> : null}
            {showAmounts ? <th className="px-4 py-3 text-right">Amount</th> : null}
            <th className="px-4 py-3">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.id}
              className={`cursor-pointer border-t border-slate-200 align-top transition hover:bg-blue-50/40 ${selectedRowId === row.id ? "bg-blue-50" : ""} ${row.excluded ? "opacity-50" : ""}`}
              onClick={() => onSelect(row)}
            >
              <td className="whitespace-nowrap px-4 py-3 font-semibold text-slate-800">{row.boq_item_number || row.subcategory_code || "—"}</td>
              <td className="min-w-[440px] px-4 py-3">
                <p className="leading-6 text-slate-800">{row.description}</p>
                <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-400">
                  <span>{row.section || "No section"}</span>
                  {row.item_code ? <span>{row.item_code}</span> : null}
                  {row.floor_names.length ? <span>{row.floor_names.join(", ")}</span> : null}
                  <span>{row.source_items.length} source item{row.source_items.length === 1 ? "" : "s"}</span>
                  {row.manual ? <span>Manual</span> : null}
                  {row.excluded ? <span className="font-semibold text-red-500">Excluded</span> : null}
                </div>
                {row.missing_fields.length ? <p className="mt-1 text-xs text-amber-700">Missing: {row.missing_fields.map((field) => field.replaceAll("_", " ")).join(", ")}</p> : null}
              </td>
              <td className="px-4 py-3">{row.unit}</td>
              <td className="px-4 py-3 text-right font-semibold text-slate-900">{quantityLabel(row)}</td>
              {showRates ? <td className="px-4 py-3 text-right">{row.rate == null ? "—" : row.rate.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td> : null}
              {showAmounts ? <td className="px-4 py-3 text-right font-semibold">{row.amount == null ? "—" : row.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td> : null}
              <td className="px-4 py-3"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${statusTone(row.status)}`}>{row.status.replaceAll("_", " ")}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length ? (
        <div className="p-16 text-center">
          <p className="font-semibold text-slate-700">No BOQ items match these filters.</p>
          <p className="mt-1 text-sm text-slate-500">Clear the filters or refresh the BOQ after Review is ready.</p>
        </div>
      ) : null}
    </div>
  );
}
