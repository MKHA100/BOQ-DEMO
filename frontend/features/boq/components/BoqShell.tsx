"use client";

import type { ReactNode } from "react";
import { WorkflowStepPage } from "@/features/workflow/components/WorkflowStepPage";

export function BoqShell({ projectId, children }: { projectId: string; children: ReactNode }) {
  return (
    <WorkflowStepPage projectId={projectId} stepKey="boq">
      {children}
    </WorkflowStepPage>
  );
}
