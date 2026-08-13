import type { ReviewFloor } from "../types";

export function ModelProcessingStatus({ floor }: { floor: ReviewFloor }) {
  const status = floor.detection_status;
  if (status === "failed") return <span className="text-xs font-semibold text-red-600">Failed</span>;
  if (status === "processing") return <span className="text-xs font-semibold text-blue-700">Processing</span>;
  if (status === "results_available") return <span className="text-xs font-semibold text-blue-700">Results available · Improving walls</span>;
  if (status === "ready") return <span className="text-xs font-semibold text-slate-500">Saved results</span>;
  return <span className="text-xs font-semibold text-slate-400">Not ready</span>;
}
