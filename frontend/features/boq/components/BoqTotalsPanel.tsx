import type { BoqState } from "../types";

export function BoqTotalsPanel({ state }: { state: BoqState }) {
  const report = state.report?.summary || {};
  const currency = state.setup.currency || "Rs";
  if (!state.setup.include_amounts) {
    return <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">Rates and amounts are hidden. Enable them in Document Setup when pricing is required.</div>;
  }
  const money = (value?: number) => `${currency} ${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <div className="rounded-xl border border-slate-200 p-4"><p className="text-xs uppercase text-slate-500">Subtotal</p><p className="mt-1 text-lg font-semibold">{money(report.subtotal)}</p></div>
      <div className="rounded-xl border border-slate-200 p-4"><p className="text-xs uppercase text-slate-500">VAT ({state.setup.vat_percentage}%)</p><p className="mt-1 text-lg font-semibold">{money(report.vat)}</p></div>
      <div className="rounded-xl border border-blue-200 bg-blue-50 p-4"><p className="text-xs uppercase text-blue-600">Grand total</p><p className="mt-1 text-lg font-semibold text-blue-900">{money(report.grand_total)}</p></div>
    </div>
  );
}
