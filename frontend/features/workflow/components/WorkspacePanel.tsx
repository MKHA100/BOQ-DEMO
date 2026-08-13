import type { ReactNode } from "react";

export function WorkspacePanel({ children, className = "" }: { children?: ReactNode; className?: string }) {
  return (
    <section className={`min-h-[520px] rounded-[24px] border border-slate-200 bg-white shadow-sm ${className}`}>
      {children}
    </section>
  );
}
