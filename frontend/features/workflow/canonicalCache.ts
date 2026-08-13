"use client";

import type { QueryClient } from "@tanstack/react-query";
import { workflowQueryKeys } from "./queryKeys";

/**
 * Marks only data derived from a canonical floor edit as stale. React Query keeps
 * the last committed value visible and quietly refetches active/mounted screens.
 */
export function markCanonicalFloorChanged(
  queryClient: QueryClient,
  projectId: string,
  floorId: string,
  options: { elements?: boolean; walls?: boolean; rooms?: boolean; review?: boolean; boq?: boolean } = {},
) {
  const targets: ReadonlyArray<readonly unknown[]> = [workflowQueryKeys.summary(projectId)];
  const keys: ReadonlyArray<readonly unknown[]> = [
    ...targets,
    ...(options.elements ? [workflowQueryKeys.elements(projectId, floorId), ["model-review", projectId]] : []),
    ...(options.walls ? [workflowQueryKeys.walls(projectId, floorId), ["walls", projectId]] : []),
    ...(options.rooms ? [workflowQueryKeys.rooms(projectId, floorId), ["floors", projectId]] : []),
    ...(options.review ? [workflowQueryKeys.review(projectId), ["review", projectId]] : []),
    ...(options.boq ? [workflowQueryKeys.boq(projectId), ["boq", projectId]] : []),
  ];
  for (const queryKey of keys) {
    void queryClient.invalidateQueries({ queryKey, refetchType: "active" });
  }
}

export function markCropReplaced(queryClient: QueryClient, projectId: string, floorId: string) {
  for (const queryKey of [
    ["floor-plans", projectId],
    workflowQueryKeys.summary(projectId),
    workflowQueryKeys.crop(projectId, floorId),
    workflowQueryKeys.calibration(projectId, floorId),
    ["model-review", projectId],
    ["walls", projectId],
    ["floors", projectId],
    ["review", projectId],
    ["boq", projectId],
  ] as const) {
    void queryClient.invalidateQueries({ queryKey, refetchType: "active" });
  }
}
