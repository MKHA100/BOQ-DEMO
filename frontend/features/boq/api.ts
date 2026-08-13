import { apiRequestHeaders, apiUrl, requestJson } from "@/shared/services/apiClient";
import type {
  BoqDocumentSetup, BoqExport, BoqState, BoqTemplateItem, BoqTemplateLibrary,
  BoqTemplatePackage,
} from "./types";

const base = (projectId: string) => `/api/v1/projects/${projectId}/boq`;

export function getBoqState(projectId: string, floorId: string | null, groupingMode: string): Promise<BoqState> {
  const params = new URLSearchParams({ grouping_mode: groupingMode });
  if (floorId) params.set("floor_id", floorId);
  return requestJson(`${base(projectId)}?${params}`);
}

export function refreshBoq(projectId: string, groupingMode: string, floorId: string | null) {
  return requestJson(`${base(projectId)}/refresh`, { method: "POST", body: JSON.stringify({ grouping_mode: groupingMode, floor_id: floorId }) });
}

export function addManualBoqRow(projectId: string, payload: {
  description: string; section: string; item_code?: string | null; quantity: number; unit: string; rate?: number | null; floor_id: string | null;
}) {
  return requestJson(`${base(projectId)}/rows`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateBoqRow(projectId: string, rowId: string, payload: Record<string, unknown>) {
  return requestJson(`${base(projectId)}/rows/${rowId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function requestBoqExport(projectId: string, format: "pdf" | "xlsx" | "csv", floorMode: string, floorId: string | null) {
  return requestJson(`${base(projectId)}/exports`, { method: "POST", body: JSON.stringify({ format, floor_mode: floorMode, floor_id: floorId }) });
}

export function getBoqExports(projectId: string): Promise<{ exports: BoqExport[]; active_jobs: Array<{ id: string; status: string; category: string }> }> {
  return requestJson(`${base(projectId)}/exports`);
}

export async function downloadBoqExport(projectId: string, exportId: string, filename: string) {
  const response = await fetch(apiUrl(`${base(projectId)}/exports/${exportId}/download`), { headers: apiRequestHeaders() });
  if (!response.ok) throw new Error("The export is not ready.");
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = filename; anchor.click();
  URL.revokeObjectURL(url);
}

export function selectBoqTemplate(projectId: string, templateId: string) {
  return requestJson(`${base(projectId)}/templates/${templateId}/select`, { method: "POST" });
}

export function getBoqSetup(projectId: string): Promise<BoqDocumentSetup> {
  return requestJson(`${base(projectId)}/setup`);
}

export function saveBoqSetup(projectId: string, payload: BoqDocumentSetup) {
  return requestJson(`${base(projectId)}/setup`, { method: "PUT", body: JSON.stringify(payload) });
}

export function getBoqTemplateLibrary(projectId: string): Promise<BoqTemplateLibrary> {
  return requestJson(`${base(projectId)}/templates`);
}

export function createBoqTemplatePackage(projectId: string, payload: { name: string; description?: string; category?: string }): Promise<BoqTemplatePackage> {
  return requestJson(`${base(projectId)}/templates`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateBoqTemplatePackage(projectId: string, templateId: string, payload: Record<string, unknown>): Promise<BoqTemplatePackage> {
  return requestJson(`${base(projectId)}/templates/${templateId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function duplicateBoqTemplatePackage(projectId: string, templateId: string, name?: string): Promise<BoqTemplatePackage> {
  return requestJson(`${base(projectId)}/templates/${templateId}/duplicate`, { method: "POST", body: JSON.stringify({ name: name || null }) });
}

export function deleteBoqTemplatePackage(projectId: string, templateId: string) {
  return requestJson(`${base(projectId)}/templates/${templateId}`, { method: "DELETE" });
}

export function createBoqTemplateItem(projectId: string, templateId: string, payload: Omit<BoqTemplateItem, "id" | "template_id">): Promise<BoqTemplateItem> {
  return requestJson(`${base(projectId)}/templates/${templateId}/items`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateBoqTemplateItem(projectId: string, templateId: string, itemId: string, payload: Partial<BoqTemplateItem>): Promise<BoqTemplateItem> {
  return requestJson(`${base(projectId)}/templates/${templateId}/items/${itemId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteBoqTemplateItem(projectId: string, templateId: string, itemId: string) {
  return requestJson(`${base(projectId)}/templates/${templateId}/items/${itemId}`, { method: "DELETE" });
}

export function previewBoqTemplateItem(projectId: string, templateId: string, itemId: string, values: Record<string, unknown> = {}): Promise<{ description: string }> {
  return requestJson(`${base(projectId)}/templates/${templateId}/items/${itemId}/preview`, { method: "POST", body: JSON.stringify({ values }) });
}
