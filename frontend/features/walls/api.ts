import { requestJson } from "@/shared/services/apiClient";
import type { WallCreatePayload, WallPatch, WallsState } from "./types";

const base = (projectId: string) => `/api/v1/projects/${projectId}/walls`;
export function getWallsState(projectId: string, floorId?: string | null): Promise<WallsState> {
  return requestJson<WallsState>(`${base(projectId)}${floorId ? `?floor_id=${encodeURIComponent(floorId)}` : ""}`);
}
export function updateWall(projectId: string, floorId: string, wallId: string, payload: WallPatch) {
  return requestJson(`${base(projectId)}/floors/${floorId}/${wallId}`, { method: "PATCH", body: JSON.stringify(payload) });
}
export function createWall(projectId: string, floorId: string, payload: WallCreatePayload) {
  return requestJson(`${base(projectId)}/floors/${floorId}`, { method: "POST", body: JSON.stringify(payload) });
}
export function deleteWall(projectId: string, floorId: string, wallId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/${wallId}`, { method: "DELETE" });
}
export function regenerateWalls(projectId: string, floorId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/regenerate`, { method: "POST" });
}
export function autoFixWalls(projectId: string, floorId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/auto-fix`, { method: "POST" });
}
export function confirmAllWalls(projectId: string, floorId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/confirm-all`, { method: "POST" });
}
export function assignOpening(projectId: string, floorId: string, wallId: string, elementId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/${wallId}/openings`, { method: "POST", body: JSON.stringify({ element_id: elementId }) });
}
export function splitWall(projectId: string, floorId: string, wallId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/${wallId}/split`, { method: "POST", body: JSON.stringify({ ratio: 0.5 }) });
}
export function mergeWall(projectId: string, floorId: string, wallId: string, otherWallId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/${wallId}/merge`, { method: "POST", body: JSON.stringify({ other_wall_id: otherWallId }) });
}
export function restoreWall(projectId: string, floorId: string, wallId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/${wallId}/restore`, { method: "POST" });
}
