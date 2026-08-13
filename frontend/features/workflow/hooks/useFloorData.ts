"use client";

import { useEffect, useMemo } from "react";
import { useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { getCachedJson } from "@/shared/services/apiClient";
import { getBoqView, getCalibration, getFloorCrop, listElements, listReviewIssues, listRooms, listWalls } from "../readApi";
import { workflowQueryKeys } from "../queryKeys";

function useCachedQuerySeed<T>(queryKey: QueryKey, path: string, enabled: boolean): void {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!enabled || !path || queryClient.getQueryData(queryKey) !== undefined) return;
    const cached = getCachedJson<T>(path);
    if (cached) queryClient.setQueryData(queryKey, cached);
  }, [enabled, path, queryClient, queryKey]);
}

export function useFloorCrop(projectId: string, floorId: string | null) {
  const path = floorId ? `/api/v1/projects/${projectId}/workflow/floors/${floorId}/crop` : "";
  const queryKey = useMemo(() => workflowQueryKeys.crop(projectId, floorId || "none"), [floorId, projectId]);
  useCachedQuerySeed(queryKey, path, Boolean(floorId));

  return useQuery({
    queryKey,
    queryFn: () => getFloorCrop(projectId, floorId as string),
    enabled: Boolean(floorId),
  });
}

export function useCalibration(projectId: string, floorId: string | null) {
  const path = floorId ? `/api/v1/projects/${projectId}/workflow/floors/${floorId}/calibration` : "";
  const queryKey = useMemo(() => workflowQueryKeys.calibration(projectId, floorId || "none"), [floorId, projectId]);
  useCachedQuerySeed(queryKey, path, Boolean(floorId));

  return useQuery({
    queryKey,
    queryFn: () => getCalibration(projectId, floorId as string),
    enabled: Boolean(floorId),
  });
}

export function useElements(projectId: string, floorId: string | null) {
  return useQuery({
    queryKey: workflowQueryKeys.elements(projectId, floorId || "none"),
    queryFn: () => listElements(projectId, floorId as string),
    enabled: Boolean(floorId),
  });
}

export function useWalls(projectId: string, floorId: string | null) {
  return useQuery({
    queryKey: workflowQueryKeys.walls(projectId, floorId || "none"),
    queryFn: () => listWalls(projectId, floorId as string),
    enabled: Boolean(floorId),
  });
}

export function useRooms(projectId: string, floorId: string | null) {
  return useQuery({
    queryKey: workflowQueryKeys.rooms(projectId, floorId || "none"),
    queryFn: () => listRooms(projectId, floorId as string),
    enabled: Boolean(floorId),
  });
}

export function useReviewIssues(projectId: string, floorId?: string) {
  return useQuery({
    queryKey: workflowQueryKeys.review(projectId, floorId),
    queryFn: () => listReviewIssues(projectId, floorId),
  });
}

export function useBoqView(projectId: string, floorId?: string) {
  return useQuery({
    queryKey: workflowQueryKeys.boq(projectId, floorId),
    queryFn: () => getBoqView(projectId, floorId),
  });
}
