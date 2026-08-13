"use client";

import { useRef, useState, type DragEvent } from "react";
import { useRouter } from "next/navigation";
import { PlatformShell } from "@/features/platform/components/PlatformShell";
import { createProject } from "@/features/projects/services/projectService";
import { uploadProjectPdf } from "@/features/upload/api";
import { Button } from "@/shared/components/Button";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import { appRoutes } from "@/shared/constants/appRoutes";

const MAX_UPLOAD_MB = Number(process.env.NEXT_PUBLIC_MAX_UPLOAD_MB || 200);

export function PdfGenerationPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [projectName, setProjectName] = useState("");
  const [projectId, setProjectId] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function selectFile(next: File | null) {
    if (!next) return;
    if (!next.name.toLowerCase().endsWith(".pdf")) {
      setError("Select a PDF file.");
      return;
    }
    if (next.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setError(`The PDF must be ${MAX_UPLOAD_MB} MB or smaller.`);
      return;
    }
    setFile(next);
    if (!projectName.trim()) setProjectName(next.name.replace(/\.pdf$/i, ""));
    setProgress(0);
    setError(null);
  }

  async function createAndUpload() {
    if (!file || !projectName.trim() || saving) return;
    setSaving(true);
    setError(null);
    try {
      let resolvedProjectId = projectId;
      if (!resolvedProjectId) {
        const project = await createProject({
          name: projectName.trim(),
          project_number: null,
          client_name: null,
          location: null,
          description: null,
        });
        resolvedProjectId = project.project_id;
        setProjectId(resolvedProjectId);
      }
      await uploadProjectPdf(resolvedProjectId, file, (next) => setProgress(next.percent));
      router.push(appRoutes.workflowStep(resolvedProjectId, "floor-plans"));
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "The project PDF could not be uploaded.");
    } finally {
      setSaving(false);
    }
  }

  function drop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    selectFile(event.dataTransfer.files?.[0] || null);
  }

  return (
    <PlatformShell title="PDF Generation" eyebrow="Workspace" activeNavHref={appRoutes.pdfGeneration}>
      <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm sm:p-8 lg:p-10">
        <div className="flex flex-col gap-3 border-b border-slate-100 pb-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-slate-950">Upload Floor Plan PDF</h2>
            <p className="mt-2 text-sm text-slate-500">Create an AutoBOQ project from the main construction drawing set.</p>
          </div>
          <span className="inline-flex w-fit rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">PDF Input</span>
        </div>

        <div className="mt-7 grid gap-7 xl:grid-cols-[minmax(0,1fr)_360px]">
          {!file ? (
            <div
              role="button"
              tabIndex={0}
              className={`flex min-h-[340px] cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed p-8 text-center transition ${
                dragging ? "border-blue-400 bg-blue-50 ring-4 ring-blue-100" : "border-slate-200 bg-slate-50/60 hover:border-blue-300 hover:bg-blue-50/40"
              }`}
              onClick={() => inputRef.current?.click()}
              onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") inputRef.current?.click(); }}
              onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={() => setDragging(false)}
              onDrop={drop}
            >
              <input ref={inputRef} type="file" accept="application/pdf,.pdf" className="hidden" onChange={(event) => selectFile(event.target.files?.[0] || null)} />
              <div className="flex h-20 w-20 items-center justify-center rounded-2xl border border-slate-200 bg-white text-lg font-bold text-red-600 shadow-sm">PDF</div>
              <p className="mt-5 text-sm text-slate-500">Drag and drop or select a PDF up to {MAX_UPLOAD_MB} MB.</p>
              <span className="mt-5 inline-flex rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white">Select PDF</span>
            </div>
          ) : (
            <div className="flex min-h-[340px] flex-col rounded-2xl border border-slate-200 bg-slate-50/60 p-6 sm:p-8">
              <span className="inline-flex w-fit rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">PDF Selected</span>
              <div className="mt-5 flex items-center gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-sm font-bold text-red-600">PDF</div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-slate-950">{file.name}</p>
                  <p className="mt-1 text-xs text-slate-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
              </div>
              {saving ? (
                <div className="mt-6">
                  <div className="flex justify-between text-xs font-semibold text-slate-500"><span>Uploading</span><span>{progress}%</span></div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-blue-600 transition-all" style={{ width: `${progress}%` }} /></div>
                </div>
              ) : null}
              <div className="mt-auto flex flex-wrap gap-3 pt-6">
                <label className="cursor-pointer rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-blue-50">
                  Replace File
                  <input type="file" accept="application/pdf,.pdf" className="hidden" disabled={saving} onChange={(event) => selectFile(event.target.files?.[0] || null)} />
                </label>
                <button type="button" disabled={saving} onClick={() => { setFile(null); setProjectId(null); setProgress(0); }} className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-600 hover:bg-rose-50 hover:text-rose-700">Remove</button>
              </div>
            </div>
          )}

          <div className="flex flex-col gap-5">
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Project Name</span>
              <input value={projectName} onChange={(event) => setProjectName(event.target.value)} disabled={saving} placeholder="Residential Plan" className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100" />
            </label>
            <Button className="w-full rounded-xl px-6 py-3" disabled={!file || !projectName.trim() || saving} onClick={() => void createAndUpload()}>
              {saving ? "Uploading PDF" : "Create Project"}
            </Button>
            {error ? <ErrorMessage message={error} /> : null}
          </div>
        </div>
      </section>
    </PlatformShell>
  );
}
