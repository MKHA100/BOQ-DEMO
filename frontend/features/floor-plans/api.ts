import { ApiRequestError, apiRequestHeaders, apiUrl, requestJson, userFacingApiError } from "@/shared/services/apiClient";
import type { FloorCropSaveInput, FloorCropSaveResult, FloorPlansState, FloorSourceUploadResult } from "./types";

const basePath = (projectId: string) => `/api/v1/projects/${projectId}/floor-plans`;

export function getFloorPlans(projectId: string): Promise<FloorPlansState> {
  return requestJson<FloorPlansState>(basePath(projectId));
}

export function updateFloorPlanSettings(
  projectId: string,
  payload: { default_wall_height_mm: number; measurement_unit: string }
): Promise<FloorPlansState> {
  return requestJson<FloorPlansState>(`${basePath(projectId)}/settings`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function addFloor(projectId: string): Promise<FloorPlansState> {
  return requestJson<FloorPlansState>(`${basePath(projectId)}/floors`, { method: "POST" });
}

export function updateFloor(
  projectId: string,
  floorId: string,
  payload: { name?: string; uses_default_height?: boolean; wall_height_mm?: number | null }
): Promise<FloorPlansState> {
  return requestJson<FloorPlansState>(`${basePath(projectId)}/floors/${floorId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function removeFloor(projectId: string, floorId: string): Promise<FloorPlansState> {
  return requestJson<FloorPlansState>(`${basePath(projectId)}/floors/${floorId}`, { method: "DELETE" });
}

export function saveFloorCrop(projectId: string, floorId: string, payload: FloorCropSaveInput): Promise<FloorCropSaveResult> {
  return requestJson<FloorCropSaveResult>(
    `${basePath(projectId)}/floors/${floorId}/crop`,
    { method: "PUT", body: JSON.stringify(payload) }
  );
}

export function prepareFloorPlanDocument(projectId: string, documentId: string): Promise<FloorPlansState> {
  return requestJson<FloorPlansState>(`${basePath(projectId)}/documents/${documentId}/prepare`, {
    method: "POST",
  });
}

export function uploadFloorSource(
  projectId: string,
  floorId: string,
  file: File,
  onProgress?: (percent: number) => void
): Promise<FloorSourceUploadResult> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", apiUrl(`${basePath(projectId)}/floors/${floorId}/source`));
    Object.entries(apiRequestHeaders()).forEach(([name, value]) => request.setRequestHeader(name, value));
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100));
    };
    request.onerror = () => reject(new ApiRequestError(0, "The floor source could not be uploaded."));
    request.onload = () => {
      let payload: unknown = null;
      try {
        payload = request.responseText ? JSON.parse(request.responseText) : null;
      } catch {
        payload = null;
      }
      if (request.status >= 200 && request.status < 300) {
        onProgress?.(100);
        resolve(payload as FloorSourceUploadResult);
        return;
      }
      const rawMessage =
        payload && typeof payload === "object" && "detail" in payload && typeof payload.detail === "string"
          ? payload.detail
          : request.statusText || "Upload failed.";
      reject(new ApiRequestError(request.status, userFacingApiError(request.status, rawMessage), rawMessage));
    };
    const body = new FormData();
    body.append("file", file);
    request.send(body);
  });
}
