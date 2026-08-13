import { ApiRequestError, apiRequestHeaders, apiUrl, getCachedJson, requestJson, setCachedJson, userFacingApiError } from "@/shared/services/apiClient";
import type { CropSourcePayload, ScopeMode, SpecificationCategoryKey, SpecificationsState } from "./types";

const base = (projectId: string) => `/api/v1/projects/${projectId}/specifications`;

export function getCachedSpecifications(projectId: string): SpecificationsState | undefined {
  return getCachedJson<SpecificationsState>(base(projectId)) ?? undefined;
}

export async function getSpecifications(projectId: string): Promise<SpecificationsState> {
  const state = await requestJson<SpecificationsState>(base(projectId));
  setCachedJson(base(projectId), state);
  return state;
}

export function cacheSpecifications(projectId: string, state: SpecificationsState): void {
  setCachedJson(base(projectId), state);
}

export function uploadSpecificationSource(
  projectId: string,
  input: {
    category: SpecificationCategoryKey;
    file: File;
    scopeMode: ScopeMode;
    floorIds: string[];
    replaceSourceId?: string;
  },
  onProgress: (percent: number) => void
): Promise<SpecificationsState> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", apiUrl(`${base(projectId)}/sources/upload`));
    Object.entries(apiRequestHeaders()).forEach(([name, value]) => request.setRequestHeader(name, value));
    request.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
    };
    request.onerror = () => reject(new ApiRequestError(0, "The file could not be uploaded. Check your connection and try again."));
    request.onload = () => {
      let payload: unknown = null;
      try {
        payload = request.responseText ? JSON.parse(request.responseText) : null;
      } catch {
        payload = null;
      }
      if (request.status >= 200 && request.status < 300) {
        onProgress(100);
        resolve((payload as { state: SpecificationsState }).state);
        return;
      }
      const raw = payload && typeof payload === "object" && "detail" in payload && typeof payload.detail === "string"
        ? payload.detail
        : request.statusText || "Upload failed.";
      reject(new ApiRequestError(request.status, userFacingApiError(request.status, raw), raw));
    };
    const body = new FormData();
    body.append("category", input.category);
    body.append("scope_mode", input.scopeMode);
    body.append("floor_ids", JSON.stringify(input.floorIds));
    if (input.replaceSourceId) body.append("replace_source_id", input.replaceSourceId);
    body.append("file", input.file);
    request.send(body);
  });
}

export function createSpecificationCrop(projectId: string, payload: CropSourcePayload): Promise<{ state: SpecificationsState }> {
  return requestJson<{ state: SpecificationsState }>(`${base(projectId)}/sources/crop`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateSourceScope(
  projectId: string,
  sourceId: string,
  scopeMode: ScopeMode,
  floorIds: string[]
): Promise<SpecificationsState> {
  return requestJson<SpecificationsState>(`${base(projectId)}/sources/${sourceId}/scope`, {
    method: "PATCH",
    body: JSON.stringify({ scope_mode: scopeMode, floor_ids: floorIds }),
  });
}

export function removeSource(projectId: string, sourceId: string): Promise<SpecificationsState> {
  return requestJson<SpecificationsState>(`${base(projectId)}/sources/${sourceId}`, { method: "DELETE" });
}

export function setCategorySkipped(
  projectId: string,
  category: SpecificationCategoryKey,
  skipped: boolean
): Promise<SpecificationsState> {
  return requestJson<SpecificationsState>(`${base(projectId)}/categories/${category}/skip`, {
    method: "POST",
    body: JSON.stringify({ skipped }),
  });
}
