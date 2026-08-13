import type { WorkflowStatus } from "../types";

const labels: Record<WorkflowStatus, string> = {
  ready: "Ready",
  results_available: "Results available",
  processing: "Processing",
  needs_review: "Needs Review",
  confirmed: "Confirmed",
  failed: "Failed",
  not_ready: "Not Ready",
};

const styles: Record<WorkflowStatus, string> = {
  ready: "border-emerald-200 bg-emerald-50 text-emerald-700",
  results_available: "border-blue-200 bg-blue-50 text-blue-700",
  processing: "border-blue-200 bg-blue-50 text-blue-700",
  needs_review: "border-amber-200 bg-amber-50 text-amber-800",
  confirmed: "border-emerald-200 bg-emerald-50 text-emerald-700",
  failed: "border-red-200 bg-red-50 text-red-700",
  not_ready: "border-slate-200 bg-slate-50 text-slate-600",
};

export function StatusBadge({ status }: { status: WorkflowStatus }) {
  return (
    <span className={`inline-flex h-7 items-center rounded-full border px-3 text-xs font-semibold ${styles[status]}`}>
      {labels[status]}
    </span>
  );
}
