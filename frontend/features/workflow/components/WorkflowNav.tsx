"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { appRoutes } from "@/shared/constants/appRoutes";
import { WORKFLOW_STEPS } from "../steps";
import type { WorkflowStepSummary } from "../types";
import { StatusBadge } from "./StatusBadge";

export function WorkflowNav({ projectId, steps }: { projectId: string; steps: WorkflowStepSummary[] }) {
  const pathname = usePathname();
  const statusByKey = new Map(steps.map((step) => [step.key, step.status]));

  return (
    <nav aria-label="PDF workflow" className="overflow-x-auto border-b border-slate-200 bg-white px-4 py-3">
      <div className="flex min-w-max items-center gap-2">
        {WORKFLOW_STEPS.filter((step) => step.key !== "upload").map((step, index) => {
          const href = appRoutes.workflowStep(projectId, step.key);
          const active = pathname === href;
          return (
            <Link
              key={step.key}
              href={href}
              className={
                active
                  ? "flex h-11 items-center gap-2 rounded-xl bg-slate-950 px-4 text-sm font-semibold text-white"
                  : "flex h-11 items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-600 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
              }
            >
              <span className={active ? "text-white/70" : "text-slate-400"}>{index + 1}</span>
              <span>{step.shortLabel}</span>
              {!active && statusByKey.get(step.key) ? <StatusBadge status={statusByKey.get(step.key)!} /> : null}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
