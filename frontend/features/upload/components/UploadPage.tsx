"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { PlatformShell } from "@/features/platform/components/PlatformShell";
import { Button } from "@/shared/components/Button";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import { appRoutes } from "@/shared/constants/appRoutes";
import { listProjectDocuments, uploadProjectPdf } from "../api";
import type { UploadDocument, UploadProgress, UploadResult } from "../types";
import { PdfUploadField } from "./PdfUploadField";

const MAX_UPLOAD_MB = Number(process.env.NEXT_PUBLIC_MAX_UPLOAD_MB || 200);

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(bytes < 10 * 1024 * 1024 ? 1 : 0)} MB`;
}

function validateFile(file: File): string | null {
  if (!file.name.toLowerCase().endsWith(".pdf")) return "Select a PDF file.";
  if (file.type && !["application/pdf", "application/x-pdf"].includes(file.type)) return "Select a valid PDF file.";
  if (file.size === 0) return "The selected PDF is empty.";
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return `The PDF must be ${MAX_UPLOAD_MB} MB or smaller.`;
  return null;
}

function FileSummary({ file, document }: { file?: File | null; document?: UploadDocument | null }) {
  const name = file?.name || document?.original_file_name || document?.file_name || "Construction PDF";
  const size = file?.size ?? document?.size_bytes ?? 0;
  const pages = document?.page_count;
  return (
    <div className="flex min-w-0 items-center gap-4">
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-slate-900 text-xs font-semibold text-white">PDF</div>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-slate-950">{name}</p>
        <p className="mt-1 text-xs text-slate-500">
          {formatBytes(size)}{pages ? ` · ${pages} page${pages === 1 ? "" : "s"}` : ""}
        </p>
      </div>
    </div>
  );
}

export function UploadPage({ projectId }: { projectId: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const documentsQuery = useQuery({
    queryKey: ["workflow-documents", projectId],
    queryFn: () => listProjectDocuments(projectId),
    staleTime: 30_000,
  });

  const currentDocument = useMemo(
    () => documentsQuery.data?.find((document) => document.is_primary) ?? documentsQuery.data?.[0] ?? null,
    [documentsQuery.data]
  );
  const savedDocument = result?.document ?? currentDocument;

  function chooseFile(file: File) {
    const message = validateFile(file);
    if (message) {
      setSelectedFile(null);
      setError(message);
      return;
    }
    setSelectedFile(file);
    setResult(null);
    setProgress(null);
    setError(null);
  }

  async function upload() {
    if (!selectedFile || uploading) return;
    setUploading(true);
    setError(null);
    setProgress({ loaded: 0, total: selectedFile.size, percent: 0 });
    try {
      const uploadResult = await uploadProjectPdf(projectId, selectedFile, setProgress);
      setResult(uploadResult);
      setSelectedFile(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["workflow-documents", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["workflow-summary", projectId] }),
      ]);
      router.push(appRoutes.workflowStep(projectId, "floor-plans"));
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "The PDF could not be uploaded.");
      setProgress(null);
    } finally {
      setUploading(false);
    }
  }

  function continueToFloorPlans() {
    router.push(appRoutes.workflowStep(projectId, "floor-plans"));
  }

  return (
    <PlatformShell title="Upload PDF" eyebrow="PDF Generation" activeNavHref={appRoutes.pdfGeneration}>
      <section className="rounded-[28px] border border-slate-200 bg-white shadow-sm">
      <div className="mx-auto flex min-h-[520px] max-w-3xl flex-col px-6 py-8 sm:px-10 sm:py-10">
        <div>
          <h3 className="text-2xl font-semibold tracking-tight text-slate-950">Upload construction PDF</h3>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            Add the main drawing set for this project. PDF files up to {MAX_UPLOAD_MB} MB are supported.
          </p>
        </div>

        <div className="mt-8">
          {!selectedFile && !savedDocument ? <PdfUploadField disabled={uploading} onSelect={chooseFile} /> : null}

          {selectedFile ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <FileSummary file={selectedFile} />
                <div className="flex gap-2">
                  <Button variant="secondary" disabled={uploading} onClick={() => setSelectedFile(null)}>Remove</Button>
                  <label className="inline-flex cursor-pointer items-center justify-center rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50">
                    Replace
                    <input
                      type="file"
                      accept="application/pdf,.pdf"
                      className="hidden"
                      disabled={uploading}
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) chooseFile(file);
                        event.target.value = "";
                      }}
                    />
                  </label>
                </div>
              </div>

              {progress ? (
                <div className="mt-6">
                  <div className="mb-2 flex justify-between text-xs font-medium text-slate-500">
                    <span>Uploading</span><span>{progress.percent}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                    <div className="h-full rounded-full bg-blue-600 transition-[width]" style={{ width: `${progress.percent}%` }} />
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}

          {!selectedFile && savedDocument ? (
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <p className="mb-3 text-sm font-semibold text-emerald-800">
                    {result?.duplicate ? "This PDF is already saved." : "PDF uploaded successfully."}
                  </p>
                  <FileSummary document={savedDocument} />
                </div>
                <label className="inline-flex cursor-pointer items-center justify-center rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50">
                  Replace
                  <input
                    type="file"
                    accept="application/pdf,.pdf"
                    className="hidden"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) chooseFile(file);
                      event.target.value = "";
                    }}
                  />
                </label>
              </div>
            </div>
          ) : null}

          {documentsQuery.isError && !savedDocument ? <div className="mt-4"><ErrorMessage message={documentsQuery.error.message} /></div> : null}
          {error ? <div className="mt-4"><ErrorMessage message={error} /></div> : null}
        </div>

        <div className="mt-auto flex flex-wrap justify-end gap-3 pt-8">
          {selectedFile ? (
            <Button className="min-w-32" disabled={uploading} onClick={upload}>
              {uploading ? "Uploading…" : "Upload PDF"}
            </Button>
          ) : null}
          {!selectedFile && savedDocument ? (
            <Button className="min-w-32" onClick={continueToFloorPlans}>Continue</Button>
          ) : null}
        </div>
      </div>
      </section>
    </PlatformShell>
  );
}
