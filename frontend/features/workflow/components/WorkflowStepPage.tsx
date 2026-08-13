"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { PlatformShell } from "@/features/platform/components/PlatformShell";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import { appRoutes } from "@/shared/constants/appRoutes";
import { useWorkflowSummary } from "../hooks/useWorkflowSummary";
import { WORKFLOW_STEPS, workflowStepIndex } from "../steps";
import type { WorkflowStepKey, WorkflowStatus } from "../types";
import { StatusBadge } from "./StatusBadge";
import { WorkflowNav } from "./WorkflowNav";
import { WorkspacePanel } from "./WorkspacePanel";

export function WorkflowStepPage({ projectId, stepKey, children }: { projectId: string; stepKey: WorkflowStepKey; children?: ReactNode }) {
  const router = useRouter();
  const summaryQuery = useWorkflowSummary(projectId);
  const stepIndex = workflowStepIndex(stepKey);
  const definition = WORKFLOW_STEPS[stepIndex];
  const summary = summaryQuery.data;

  useEffect(() => {
    const nextStep = WORKFLOW_STEPS[stepIndex + 1];
    if (nextStep) router.prefetch(appRoutes.workflowStep(projectId, nextStep.key));
  }, [projectId, router, stepIndex]);

  const currentStep = summary?.steps.find((step) => step.key === stepKey);
  const status: WorkflowStatus = currentStep?.status ?? "not_ready";

  return (
    <PlatformShell
      title={summary?.project.name || "Project"}
      eyebrow="PDF Generation"
      activeNavHref={appRoutes.pdfGeneration}
    >
      <div className="overflow-hidden rounded-[28px] border border-slate-200 bg-[#f7f9fc] shadow-sm">
        <WorkflowNav projectId={projectId} steps={summary?.steps || []} />
        <div className="flex min-h-20 flex-wrap items-center justify-between gap-4 border-b border-slate-200 bg-white px-6 py-4">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold tracking-tight text-slate-950">{definition.label}</h2>
            <StatusBadge status={status} />
          </div>
        </div>
        <div className="p-5 lg:p-6">
          {summaryQuery.error ? <div className="mb-4"><ErrorMessage message={summaryQuery.error.message} /></div> : null}
          <WorkspacePanel>
            {summaryQuery.isPending && !summary ? (
              <div className="h-1 w-full overflow-hidden rounded-t-[24px] bg-slate-100">
                <div className="h-full w-1/3 animate-pulse bg-blue-500" />
              </div>
            ) : null}
            {children}
          </WorkspacePanel>
        </div>
      </div>
    </PlatformShell>
  );
}
