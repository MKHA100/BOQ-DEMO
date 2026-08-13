"use client";

import type { GeometryRevision } from "../types";

export function RoomEditHistory({ items, onRestore }: { items: GeometryRevision[]; onRestore: (id: string) => void }) {
  if (!items.length) return <p className="text-xs text-slate-500">No saved geometry revisions yet.</p>;
  return (
    <div className="space-y-2">
      {items.slice(0, 8).map((item) => (
        <div key={item.id} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-xs">
          <div><strong>Revision {item.revision}</strong><div className="text-slate-500">{item.action.replaceAll("_", " ")}</div></div>
          <button className="font-semibold text-blue-600" onClick={() => onRestore(item.id)}>Restore</button>
        </div>
      ))}
    </div>
  );
}
