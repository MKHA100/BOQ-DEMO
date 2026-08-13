"use client";

import { useEffect, useMemo } from "react";
import { usePathname } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getCachedJson } from "@/shared/services/apiClient";
import { getWorkflowSummary } from "../api";
import { workflowQueryKeys } from "../queryKeys";
import type { ProjectWorkflowSummary } from "../types";

export function useWorkflowSummary(projectId: string) {
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const activeStep = pathname.split("/").filter(Boolean).at(-1) || "";
  const path = `/api/v1/projects/${projectId}/workflow/summary?active_step=${encodeURIComponent(activeStep)}`;
  const queryKey = useMemo(() => [...workflowQueryKeys.summary(projectId), activeStep] as const, [activeStep, projectId]);

  const query = useQuery({
    queryKey,
    queryFn: () => getWorkflowSummary(projectId, activeStep),
    refetchInterval: (currentQuery) => (currentQuery.state.data?.active_jobs.length ? 2_000 : false),
    refetchOnMount: "always",
    refetchOnWindowFocus: false,
    staleTime: 0,
    gcTime: 60 * 60_000,
  });

  useEffect(() => {
    if (queryClient.getQueryData(queryKey) !== undefined) return;
    const cached = getCachedJson<ProjectWorkflowSummary>(path);
    if (cached) queryClient.setQueryData(queryKey, cached);
  }, [path, queryClient, queryKey]);

  return query;
}
