"use client";

import type { Point } from "@/features/drawing/types";
import { Button } from "@/shared/components/Button";
import type { AutoFixPreview } from "../types";

export function RoomAutoFixPreviewDialog({
  preview,
  onClose,
  onApply,
}: {
  preview: AutoFixPreview;
  onClose: () => void;
  onApply: () => void;
}) {
  return (
    <div className="fixed inset-0 z-[1100] flex items-center justify-center bg-slate-950/45 p-5" role="dialog" aria-modal="true" aria-label="Auto-fix preview">
      <div className="w-full max-w-4xl overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-5">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Auto-fix preview</h2>
            <p className="mt-1 text-sm text-slate-500">The model locates the room; wall faces define the proposed BOQ boundary.</p>
          </div>
          <button type="button" className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className="grid gap-5 p-6 md:grid-cols-2">
          <PolygonPreview title="Current shape" points={preview.original.points} />
          <PolygonPreview title="Proposed shape" points={preview.proposed.points} emphasized />
        </div>

        <div className="grid gap-3 border-y border-slate-200 bg-slate-50 px-6 py-4 text-sm sm:grid-cols-4">
          <Stat label="Points" value={`${preview.original_vertex_count} → ${preview.proposed_vertex_count}`} />
          <Stat label="Shape" value={humanize(preview.shape_type || "polygon")} />
          <Stat label="Area change" value={`${preview.area_change_percent > 0 ? "+" : ""}${preview.area_change_percent.toFixed(2)}%`} />
          <Stat label="Boundary source" value={humanize(preview.source)} />
        </div>

        {preview.warnings.length ? (
          <div className="mx-6 mt-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {preview.warnings.map((warning) => <p key={warning}>{warning}</p>)}
          </div>
        ) : null}
        {!preview.changed ? (
          <div className="mx-6 mt-5 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
            No safer automatic change was found. You can still enter Edit shape and adjust points manually.
          </div>
        ) : null}

        <div className="flex justify-end gap-3 px-6 py-5">
          <Button type="button" variant="secondary" onClick={onClose}>Keep original</Button>
          <Button type="button" disabled={!preview.changed} onClick={onApply}>Apply to editor</Button>
        </div>
      </div>
    </div>
  );
}

function PolygonPreview({ title, points, emphasized = false }: { title: string; points: Point[]; emphasized?: boolean }) {
  const bounds = getBounds(points);
  const padding = Math.max(bounds.width, bounds.height) * 0.12 + 4;
  const viewBox = `${bounds.minX - padding} ${bounds.minY - padding} ${bounds.width + padding * 2} ${bounds.height + padding * 2}`;
  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <p className="mb-3 text-sm font-semibold text-slate-700">{title}</p>
      <div className="h-64 overflow-hidden rounded-lg bg-slate-100">
        <svg className="h-full w-full" viewBox={viewBox} preserveAspectRatio="xMidYMid meet">
          <polygon
            points={points.map((point) => `${point.x},${point.y}`).join(" ")}
            fill={emphasized ? "rgba(37,99,235,.16)" : "rgba(100,116,139,.12)"}
            stroke={emphasized ? "#2563eb" : "#64748b"}
            strokeWidth={Math.max(bounds.width, bounds.height) / 160}
            vectorEffect="non-scaling-stroke"
          />
          {points.map((point, index) => (
            <circle key={`${point.x}-${point.y}-${index}`} cx={point.x} cy={point.y} r={Math.max(bounds.width, bounds.height) / 90} fill={emphasized ? "#2563eb" : "#64748b"} />
          ))}
        </svg>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div><p className="text-xs uppercase tracking-wide text-slate-400">{label}</p><p className="mt-1 font-semibold text-slate-800">{value}</p></div>;
}

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function getBounds(points: Point[]) {
  if (!points.length) return { minX: 0, minY: 0, width: 1, height: 1 };
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  return { minX, minY, width: Math.max(1, Math.max(...xs) - minX), height: Math.max(1, Math.max(...ys) - minY) };
}
