import type { ScaleStatus } from "../types";

const labels: Record<ScaleStatus, string> = {
  not_calibrated: "Not Calibrated",
  in_progress: "In Progress",
  calibrated: "Calibrated",
  needs_review: "Needs Review",
  failed: "Failed",
};

export function ScaleStatusPill({ status }: { status: ScaleStatus }) {
  const style = status === "calibrated"
    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
    : status === "needs_review"
      ? "border-amber-200 bg-amber-50 text-amber-700"
      : status === "failed"
        ? "border-red-200 bg-red-50 text-red-700"
        : "border-slate-200 bg-slate-50 text-slate-600";
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold ${style}`}>{labels[status]}</span>;
}
