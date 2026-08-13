import type { WorkflowStepKey } from "./types";

export type WorkflowStepDefinition = {
  key: WorkflowStepKey;
  label: string;
  shortLabel: string;
};

export const WORKFLOW_STEPS: WorkflowStepDefinition[] = [
  { key: "upload", label: "Upload PDF", shortLabel: "Upload" },
  { key: "floor-plans", label: "Floor Plans", shortLabel: "Plans" },
  { key: "specifications", label: "Schedules & Specifications", shortLabel: "Specifications" },
  { key: "scale", label: "Scale", shortLabel: "Scale" },
  { key: "model-review", label: "Model Review", shortLabel: "Model" },
  { key: "walls", label: "Walls", shortLabel: "Walls" },
  { key: "floors", label: "Floors", shortLabel: "Floors" },
  { key: "review", label: "Review", shortLabel: "Review" },
  { key: "boq", label: "BOQ", shortLabel: "BOQ" },
];

export function workflowStepIndex(step: WorkflowStepKey) {
  return WORKFLOW_STEPS.findIndex((item) => item.key === step);
}
