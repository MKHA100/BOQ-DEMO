import { getCachedJson, requestJson, setCachedJson } from "@/shared/services/apiClient";
import type {
  ProjectCreateInput,
  ProjectCreateResponse,
  ProjectListResponse,
  ProjectResponse,
  ProjectUpdateInput,
} from "@/shared/types/apiTypes";

const PROJECT_LIST_PATH = "/api/v1/projects";

export type ProjectListOptions = {
  search?: string;
  status?: string;
  limit?: number;
  offset?: number;
};

function listPath(options: ProjectListOptions = {}): string {
  const params = new URLSearchParams();
  if (options.search?.trim()) params.set("search", options.search.trim());
  if (options.status) params.set("status", options.status);
  params.set("limit", String(options.limit ?? 24));
  params.set("offset", String(options.offset ?? 0));
  return `${PROJECT_LIST_PATH}?${params.toString()}`;
}

export function getCachedProjects(): ProjectListResponse | null {
  return getCachedJson<ProjectListResponse>(listPath());
}

export async function listProjects(options: ProjectListOptions = {}): Promise<ProjectListResponse> {
  const path = listPath(options);
  const response = await requestJson<ProjectListResponse>(path);
  setCachedJson(path, response);
  return response;
}

export function getProject(projectId: string): Promise<ProjectResponse> {
  return requestJson<ProjectResponse>(`${PROJECT_LIST_PATH}/${projectId}`);
}

export function createProject(payload: ProjectCreateInput): Promise<ProjectCreateResponse> {
  return requestJson<ProjectCreateResponse>(PROJECT_LIST_PATH, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateProject(projectId: string, payload: ProjectUpdateInput): Promise<ProjectResponse> {
  return requestJson<ProjectResponse>(`${PROJECT_LIST_PATH}/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteProject(projectId: string): Promise<void> {
  await requestJson(`${PROJECT_LIST_PATH}/${projectId}`, { method: "DELETE" });
}
