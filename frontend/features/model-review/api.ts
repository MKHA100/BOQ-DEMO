import { requestJson } from "@/shared/services/apiClient";
import type { ElementInput, ElementPatch, ModelReviewState, ReviewElement } from "./types";

const base = (projectId: string) => `/api/v1/projects/${projectId}/model-review`;

export function getModelReviewState(projectId: string, floorId?: string | null): Promise<ModelReviewState> {
  const query = floorId ? `?floor_id=${encodeURIComponent(floorId)}` : "";
  return requestJson<ModelReviewState>(`${base(projectId)}${query}`);
}

export function createReviewElement(projectId: string, floorId: string, payload: ElementInput) {
  return requestJson<{ record: ReviewElement; jobs: unknown[] }>(`${base(projectId)}/floors/${floorId}/elements`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateReviewElement(projectId: string, floorId: string, elementId: string, payload: ElementPatch) {
  return requestJson<{ record: ReviewElement; jobs: unknown[] }>(`${base(projectId)}/floors/${floorId}/elements/${elementId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function updateReviewProperty(projectId: string, floorId: string, elementId: string, propertyName: string, value: unknown, unit?: string | null) {
  return requestJson(`${base(projectId)}/floors/${floorId}/elements/${elementId}/properties/${propertyName}`, {
    method: "PATCH",
    body: JSON.stringify({ value, unit, confirm: true }),
  });
}

export function assignScheduleEntry(projectId: string, floorId: string, elementId: string, scheduleEntryId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/elements/${elementId}/schedule`, {
    method: "PUT",
    body: JSON.stringify({ schedule_entry_id: scheduleEntryId }),
  });
}

export function confirmReviewElements(projectId: string, floorId: string, elementIds: string[]) {
  return requestJson(`${base(projectId)}/floors/${floorId}/confirm`, {
    method: "POST",
    body: JSON.stringify({ element_ids: elementIds }),
  });
}
