import type { ReactNode } from "react";

export function InspectorPanel({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <aside className="rounded-[20px] border border-slate-200 bg-white shadow-sm">
      <header className="border-b border-slate-200 px-5 py-4">
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      </header>
      <div className="p-5">{children}</div>
    </aside>
  );
}
