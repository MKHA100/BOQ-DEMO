"use client";

import type { JobRun } from "../types";

export function hasActiveJobs(
  jobs: Array<Pick<JobRun, "task_type" | "status" | "floor_id">>,
  taskTypes: readonly string[],
  floorId?: string | null,
): boolean {
  const allowed = new Set(taskTypes);
  return jobs.some((job) =>
    (job.status === "pending" || job.status === "running")
    && allowed.has(job.task_type)
    && (!floorId || !job.floor_id || job.floor_id === floorId),
  );
}

export function activeJobPollInterval(active: boolean): number | false {
  return active ? 2_000 : false;
}
