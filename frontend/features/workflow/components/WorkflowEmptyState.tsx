import type { ReactNode } from "react";

export function WorkflowEmptyState({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="flex min-h-[360px] flex-col items-center justify-center px-6 text-center">
      <h2 className="text-base font-semibold text-slate-800">{title}</h2>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
