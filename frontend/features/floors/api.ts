import { requestJson } from "@/shared/services/apiClient";
import type { AutoFixPreview, FloorInterpretationStatus, FloorsState, RoomPatch } from "./types";

const base = (projectId: string) => `/api/v1/projects/${projectId}/floors`;

export function getFloorsState(projectId: string, floorId?: string | null): Promise<FloorsState> {
  return requestJson(`${base(projectId)}${floorId ? `?floor_id=${encodeURIComponent(floorId)}` : ""}`);
}

export function analyzeRooms(projectId: string, floorId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/analyze`, { method: "POST" });
}

export function recalculateRooms(projectId: string, floorId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/recalculate`, { method: "POST" });
}

export function confirmAllRooms(projectId: string, floorId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/confirm-all`, { method: "POST" });
}

export function createRoom(projectId: string, floorId: string, payload: RoomPatch) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateRoom(projectId: string, floorId: string, roomId: string, payload: RoomPatch) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteRoom(projectId: string, floorId: string, roomId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}`, { method: "DELETE" });
}

export function confirmRoom(projectId: string, floorId: string, roomId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/confirm`, { method: "POST" });
}

export function excludeRoom(projectId: string, floorId: string, roomId: string, reason?: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/exclude`, {
    method: "POST",
    body: JSON.stringify({ reason: reason || null }),
  });
}

export function splitRoom(
  projectId: string,
  floorId: string,
  roomId: string,
  axis: "horizontal" | "vertical",
) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/split`, {
    method: "POST",
    body: JSON.stringify({ axis, ratio: 0.5 }),
  });
}

export function mergeRoom(projectId: string, floorId: string, roomId: string, otherRoomId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/merge`, {
    method: "POST",
    body: JSON.stringify({ other_room_id: otherRoomId }),
  });
}

export function restoreRoom(projectId: string, floorId: string, roomId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/restore`, { method: "POST" });
}

export function acceptRoomSuggestion(projectId: string, floorId: string, suggestionId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/suggestions/${suggestionId}/accept`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function correctRoomSuggestionWithWalls(projectId: string, floorId: string, suggestionId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/suggestions/${suggestionId}/correct-with-walls`, {
    method: "POST",
  });
}

export function rejectRoomSuggestion(projectId: string, floorId: string, suggestionId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/suggestions/${suggestionId}/reject`, {
    method: "POST",
  });
}

export function splitRoomWithLine(projectId: string, floorId: string, roomId: string, points: Array<{ x: number; y: number }>) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/split-line`, {
    method: "POST", body: JSON.stringify({ points }),
  });
}

export function snapRoomToWalls(projectId: string, floorId: string, roomId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/snap`, { method: "POST" });
}

export function createFinishZone(projectId: string, floorId: string, roomId: string, payload: { points: Array<{ x: number; y: number }>; name?: string; floor_type_code?: string; floor_finish?: string }) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/finish-zones`, {
    method: "POST", body: JSON.stringify(payload),
  });
}

export function updateFinishZone(projectId: string, floorId: string, roomId: string, zoneId: string, payload: Record<string, unknown>) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/finish-zones/${zoneId}`, {
    method: "PATCH", body: JSON.stringify(payload),
  });
}

export function deleteFinishZone(projectId: string, floorId: string, roomId: string, zoneId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/finish-zones/${zoneId}`, { method: "DELETE" });
}

export function precisionRefineRooms(projectId: string, floorId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/precision-refine`, { method: "POST" });
}

export function interpretFloorRooms(projectId: string, floorId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/interpret`, { method: "POST" });
}

export function getFloorInterpretationStatus(projectId: string, floorId: string) {
  return requestJson<FloorInterpretationStatus>(`${base(projectId)}/floors/${floorId}/interpretation-status`);
}

export function previewAutoFixRoom(projectId: string, floorId: string, roomId: string) {
  return requestJson<AutoFixPreview>(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/auto-fix-preview`);
}

export function autoFixRoom(projectId: string, floorId: string, roomId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/auto-fix`, { method: "POST" });
}

export function simplifyRoomGeometry(projectId: string, floorId: string, roomId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/simplify`, { method: "POST" });
}

export function makeRoomRectangle(projectId: string, floorId: string, roomId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/make-rectangle`, { method: "POST" });
}

export function straightenRoomGeometry(projectId: string, floorId: string, roomId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/straighten`, { method: "POST" });
}

export function patchRoomGeometry(projectId: string, floorId: string, roomId: string, payload: Record<string, unknown>) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/geometry`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function createRoomCutout(projectId: string, floorId: string, roomId: string, points: Array<{ x: number; y: number }>, name?: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/cutouts`, {
    method: "POST",
    body: JSON.stringify({ points, name: name || null }),
  });
}

export function deleteRoomCutout(projectId: string, floorId: string, roomId: string, cutoutId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/cutouts/${cutoutId}`, { method: "DELETE" });
}

export function getRoomRevisions(projectId: string, floorId: string, roomId: string) {
  return requestJson<{ items: import("./types").GeometryRevision[] }>(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/revisions`);
}

export function restoreRoomRevision(projectId: string, floorId: string, roomId: string, revisionId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/revisions/${revisionId}/restore`, { method: "POST" });
}
export function loadRoomSuggestions(projectId: string, floorId: string) {
  return requestJson<{ items: import("./types").RoomSuggestion[] }>(`${base(projectId)}/floors/${floorId}/suggestions`);
}

export function resetRoomToModel(projectId: string, floorId: string, roomId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/reset-to-model`, { method: "POST" });
}

export function resetRoomToCorrected(projectId: string, floorId: string, roomId: string) {
  return requestJson(`${base(projectId)}/floors/${floorId}/rooms/${roomId}/reset-to-corrected`, { method: "POST" });
}
