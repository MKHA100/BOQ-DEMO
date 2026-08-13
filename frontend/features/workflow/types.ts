export type WorkflowStatus = "ready" | "results_available" | "processing" | "needs_review" | "confirmed" | "failed" | "not_ready";

export type WorkflowStepKey =
  | "upload"
  | "floor-plans"
  | "specifications"
  | "scale"
  | "model-review"
  | "walls"
  | "floors"
  | "review"
  | "boq";

export type VersionSet = {
  crop_version?: number;
  schedule_version?: number;
  scale_version?: number;
  element_version?: number;
  wall_version?: number;
  room_version?: number;
  review_version?: number;
  boq_version?: number;
  document_version?: number;
  specification_version?: number;
};

export type FloorSummary = {
  id: string;
  project_id: string;
  name: string;
  level_index: number;
  status: WorkflowStatus;
  versions: VersionSet;
  counts: {
    elements: number;
    walls: number;
    rooms: number;
    review_issues: number;
  };
};

export type WorkflowStepSummary = {
  key: WorkflowStepKey;
  label: string;
  status: WorkflowStatus;
};

export type JobRun = {
  id: string;
  project_id: string | null;
  floor_id: string | null;
  category: string;
  task_type: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  message: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectWorkflowSummary = {
  project: {
    id: string;
    name: string;
    status: string;
    created_at: string;
    updated_at: string;
  };
  project_versions: VersionSet;
  floors: FloorSummary[];
  counts: Record<string, number>;
  steps: WorkflowStepSummary[];
  active_jobs: JobRun[];
  updated_at: string;
};

export type MutationResult<TRecord = Record<string, unknown>> = {
  record: TRecord;
  protected: boolean;
  changed: boolean;
  versions: VersionSet;
  jobs: Array<JobRun & { created?: boolean }>;
};

export type FloorRecord = {
  id: string;
  project_id: string;
  name: string;
  level_index: number;
  status: WorkflowStatus;
  created_at: string;
  updated_at: string;
  versions: VersionSet;
};

export type ValueSource =
  | "user_confirmed"
  | "schedule"
  | "specification"
  | "drawing_note"
  | "model"
  | "calculated"
  | "default";
