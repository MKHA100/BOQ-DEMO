import { ApiRequestError, apiRequestHeaders, apiUrl, requestJson, userFacingApiError } from "@/shared/services/apiClient";
import type { UploadDocument, UploadProgress, UploadResult } from "./types";

export function listProjectDocuments(projectId: string): Promise<UploadDocument[]> {
  return requestJson<UploadDocument[]>(`/api/v1/projects/${projectId}/workflow/documents`);
}

export function uploadProjectPdf(
  projectId: string,
  file: File,
  onProgress: (progress: UploadProgress) => void
): Promise<UploadResult> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", apiUrl(`/api/v1/projects/${projectId}/workflow/documents`));
    const headers = apiRequestHeaders();
    Object.entries(headers).forEach(([name, value]) => request.setRequestHeader(name, value));

    request.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      onProgress({
        loaded: event.loaded,
        total: event.total,
        percent: Math.min(100, Math.round((event.loaded / event.total) * 100)),
      });
    };

    request.onerror = () => reject(new ApiRequestError(0, "The PDF could not be uploaded. Check your connection and try again."));
    request.onabort = () => reject(new ApiRequestError(0, "The upload was cancelled."));
    request.onload = () => {
      let payload: unknown = null;
      try {
        payload = request.responseText ? JSON.parse(request.responseText) : null;
      } catch {
        payload = null;
      }

      if (request.status >= 200 && request.status < 300) {
        onProgress({ loaded: file.size, total: file.size, percent: 100 });
        resolve(payload as UploadResult);
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
    body.append("document_type", "source");
    request.send(body);
  });
}
