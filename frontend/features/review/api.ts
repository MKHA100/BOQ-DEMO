import { requestJson } from "@/shared/services/apiClient";
import type { ReviewState } from "./types";
const base = (projectId: string) => `/api/v1/projects/${projectId}/review`;
export function getReviewState(projectId: string, floorId: string | null, category: string): Promise<ReviewState> {
  const params = new URLSearchParams(); if (floorId) params.set("floor_id", floorId); params.set("category", category);
  return requestJson(`${base(projectId)}?${params.toString()}`);
}
export function updateReviewField(projectId: string, itemId: string, field: string, value: unknown) { return requestJson(`${base(projectId)}/items/${itemId}`, { method: "PATCH", body: JSON.stringify({ field, value }) }); }
export function confirmReview(projectId: string, itemIds: string[], scope: "selected" | "floor" | "project", floorId?: string | null) { return requestJson(`${base(projectId)}/confirm`, { method: "POST", body: JSON.stringify({ item_ids: itemIds, scope, floor_id: floorId || null }) }); }
