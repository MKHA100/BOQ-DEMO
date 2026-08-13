"use client";

import { Button } from "@/shared/components/Button";

export function ReplaceCropDialog({ floorName, busy, onCancel, onConfirm }: {
  floorName: string;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="fixed inset-0 z-[130] flex items-center justify-center bg-slate-950/35 p-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl">
        <h3 className="text-lg font-semibold text-slate-950">Replace {floorName} crop?</h3>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          Generated detections from the previous crop will be replaced. Matching confirmed edits and manual items will be preserved.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="secondary" disabled={busy} onClick={onCancel}>Cancel</Button>
          <Button disabled={busy} onClick={onConfirm}>{busy ? "Saving" : "Replace crop"}</Button>
        </div>
      </div>
    </div>
  );
}
