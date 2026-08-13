"use client";

import { useQuery } from "@tanstack/react-query";
import { getBoqState } from "../api";

export const boqQueryKey = (projectId: string, floorId: string | null, grouping: string) => ["boq", projectId, floorId, grouping] as const;

export function useBoqState(projectId: string, floorId: string | null, grouping: string) {
  return useQuery({
    queryKey: boqQueryKey(projectId, floorId, grouping),
    queryFn: () => getBoqState(projectId, floorId, grouping),
    refetchOnWindowFocus: false,
    refetchOnMount: "always",
    staleTime: 0,
    placeholderData: (previous) => previous,
    refetchInterval: (query) => query.state.data?.active_jobs.length ? 2000 : false,
  });
}
