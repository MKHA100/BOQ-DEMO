import type { SpecificationStatus } from "../types";

const labels: Record<SpecificationStatus, string> = {
  ready: "Ready",
  processing: "Processing",
  needs_review: "Needs Review",
  failed: "Failed",
  skipped: "Skipped",
};

const styles: Record<SpecificationStatus, string> = {
  ready: "border-emerald-200 bg-emerald-50 text-emerald-700",
  processing: "border-blue-200 bg-blue-50 text-blue-700",
  needs_review: "border-amber-200 bg-amber-50 text-amber-700",
  failed: "border-rose-200 bg-rose-50 text-rose-700",
  skipped: "border-slate-200 bg-slate-100 text-slate-600",
};

export function StatusPill({ status }: { status: SpecificationStatus }) {
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${styles[status]}`}>{labels[status]}</span>;
}
