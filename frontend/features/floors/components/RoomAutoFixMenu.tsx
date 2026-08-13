"use client";

import { Button } from "@/shared/components/Button";

export function RoomAutoFixMenu({ disabled, onAutoFix, onSnap, onSimplify, onRectangle }: {
  disabled?: boolean;
  onAutoFix: () => void;
  onSnap: () => void;
  onSimplify: () => void;
  onRectangle: () => void;
}) {
  return (
    <details className="relative">
      <summary className="list-none"><Button variant="secondary" disabled={disabled}>Auto-fix ▾</Button></summary>
      <div className="absolute right-0 z-40 mt-2 w-48 rounded-xl border border-slate-200 bg-white p-2 shadow-xl">
        <button className="w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-slate-50" onClick={onAutoFix}>Full auto-fix</button>
        <button className="w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-slate-50" onClick={onSnap}>Snap to walls</button>
        <button className="w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-slate-50" onClick={onSimplify}>Remove extra points</button>
        <button className="w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-slate-50" onClick={onRectangle}>Make rectangle</button>
      </div>
    </details>
  );
}
