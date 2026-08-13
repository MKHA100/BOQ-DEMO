import { requestJson } from "@/shared/services/apiClient";
import type {
  FloorRecord,
  MutationResult,
  ProjectWorkflowSummary,
  ValueSource,
} from "./types";

function workflowPath(projectId: string, suffix = "") {
  return `/api/v1/projects/${projectId}/workflow${suffix}`;
}

export function getWorkflowSummary(projectId: string, activeStep?: string): Promise<ProjectWorkflowSummary> {
  const query = activeStep ? `?active_step=${encodeURIComponent(activeStep)}` : "";
  return requestJson<ProjectWorkflowSummary>(`${workflowPath(projectId, "/summary")}${query}`);
}

export function listFloors(projectId: string): Promise<FloorRecord[]> {
  return requestJson<FloorRecord[]>(workflowPath(projectId, "/floors"));
}

export function createFloor(projectId: string, payload: { name?: string; level_index?: number }): Promise<FloorRecord> {
  return requestJson<FloorRecord>(workflowPath(projectId, "/floors"), {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function uploadDocument(projectId: string, file: File, documentType = "source") {
  const body = new FormData();
  body.append("file", file);
  body.append("document_type", documentType);
  return requestJson(workflowPath(projectId, "/documents"), { method: "POST", body });
}

export function updateElementProperty(
  projectId: string,
  elementId: string,
  propertyName: string,
  payload: { value: unknown; unit?: string; source: ValueSource; confirm?: boolean }
): Promise<MutationResult> {
  return requestJson<MutationResult>(
    workflowPath(projectId, `/elements/${elementId}/properties/${propertyName}`),
    { method: "PATCH", body: JSON.stringify(payload) }
  );
}

export function saveCalibration(
  projectId: string,
  floorId: string,
  payload: {
    point_a: { x: number; y: number };
    point_b: { x: number; y: number };
    real_distance: number;
    unit: "mm" | "cm" | "m" | "in" | "ft";
    source_crop_version: number;
  }
): Promise<MutationResult> {
  return requestJson<MutationResult>(workflowPath(projectId, `/floors/${floorId}/calibration`), {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function updateRoomGeometry(
  projectId: string,
  roomId: string,
  geometry: Record<string, unknown>,
  confirm = false
): Promise<MutationResult> {
  return requestJson<MutationResult>(workflowPath(projectId, `/rooms/${roomId}/geometry`), {
    method: "PATCH",
    body: JSON.stringify({ geometry, confirm }),
  });
}
