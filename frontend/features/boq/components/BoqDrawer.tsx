"use client";

import type { ReactNode } from "react";

export function BoqDrawer({
  open,
  title,
  subtitle,
  width = "max-w-xl",
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  subtitle?: string;
  width?: string;
  onClose: () => void;
  children: ReactNode;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[90] flex justify-end bg-slate-950/35 backdrop-blur-[1px]" role="dialog" aria-modal="true" aria-label={title}>
      <button type="button" className="min-w-0 flex-1 cursor-default" aria-label="Close" onClick={onClose} />
      <section className={`flex h-full w-full ${width} flex-col bg-white shadow-2xl`}>
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-5">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
            {subtitle ? <p className="mt-1 text-sm leading-5 text-slate-500">{subtitle}</p> : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 text-lg text-slate-500 hover:bg-slate-50 hover:text-slate-900"
            aria-label="Close"
          >
            ×
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      </section>
    </div>
  );
}
