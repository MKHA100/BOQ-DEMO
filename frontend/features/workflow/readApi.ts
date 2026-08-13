import { requestJson } from "@/shared/services/apiClient";
import type {
  BoqView,
  CalibrationRecord,
  DocumentPageRecord,
  ElementRecord,
  FloorCropRecord,
  PagedResult,
  ReviewIssueRecord,
  RoomRecord,
  WallRecord,
} from "./readTypes";

function workflowPath(projectId: string, suffix: string, query?: Record<string, string | number | undefined>) {
  const params = new URLSearchParams();
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== "") params.set(key, String(value));
  });
  const search = params.toString();
  return `/api/v1/projects/${projectId}/workflow${suffix}${search ? `?${search}` : ""}`;
}

export function listDocumentPages(projectId: string, documentId: string) {
  return requestJson<DocumentPageRecord[]>(workflowPath(projectId, `/documents/${documentId}/pages`));
}

export function getFloorCrop(projectId: string, floorId: string) {
  return requestJson<FloorCropRecord | null>(workflowPath(projectId, `/floors/${floorId}/crop`));
}

export function getCalibration(projectId: string, floorId: string) {
  return requestJson<CalibrationRecord | null>(workflowPath(projectId, `/floors/${floorId}/calibration`));
}

export function listElements(projectId: string, floorId: string, limit = 100, offset = 0) {
  return requestJson<PagedResult<ElementRecord>>(
    workflowPath(projectId, `/floors/${floorId}/elements`, { limit, offset })
  );
}

export function listWalls(projectId: string, floorId: string, limit = 100, offset = 0) {
  return requestJson<PagedResult<WallRecord>>(
    workflowPath(projectId, `/floors/${floorId}/walls`, { limit, offset })
  );
}

export function listRooms(projectId: string, floorId: string, limit = 100, offset = 0) {
  return requestJson<PagedResult<RoomRecord>>(
    workflowPath(projectId, `/floors/${floorId}/rooms`, { limit, offset })
  );
}

export function listReviewIssues(projectId: string, floorId?: string, limit = 100, offset = 0) {
  return requestJson<PagedResult<ReviewIssueRecord>>(
    workflowPath(projectId, "/review-issues", { floor_id: floorId, limit, offset })
  );
}

export function getBoqView(projectId: string, floorId?: string, limit = 100, offset = 0) {
  return requestJson<BoqView>(workflowPath(projectId, "/boq", { floor_id: floorId, limit, offset }));
}
