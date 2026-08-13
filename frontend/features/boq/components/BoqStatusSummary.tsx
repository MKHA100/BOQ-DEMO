import type { BoqSummary } from "../types";

export function BoqStatusSummary({
  summary,
  totalAmount,
  currency,
  showAmount,
}: {
  summary: BoqSummary;
  totalAmount: number;
  currency: string;
  showAmount: boolean;
}) {
  const cards: Array<[string, string | number, string]> = [
    ["Items", summary.rows, "bg-white text-slate-900"],
    ["Ready", summary.ready, "bg-emerald-50 text-emerald-800"],
    ["Needs Review", summary.needs_review, "bg-amber-50 text-amber-800"],
    ["Total Amount", showAmount ? `${currency} ${totalAmount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "Not priced", "bg-blue-50 text-blue-900"],
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {cards.map(([label, value, tone]) => (
        <div key={label} className={`rounded-xl border border-slate-200 px-4 py-3 ${tone}`}>
          <p className="text-[11px] font-semibold uppercase tracking-wide opacity-65">{label}</p>
          <p className="mt-1 truncate text-xl font-semibold">{value}</p>
        </div>
      ))}
    </div>
  );
}
