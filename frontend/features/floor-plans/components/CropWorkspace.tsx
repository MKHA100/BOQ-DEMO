"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/shared/components/Button";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import type { FloorCropSaveInput, FloorCropSaveResult, FloorPlanDocument, FloorPlanFloor, FloorPlanPage, Rect } from "../types";
import { prepareFloorPlanDocument, saveFloorCrop, uploadFloorSource } from "../api";
import { fromOriginalPageRect, toOriginalPageRect, type Rotation } from "../utils/coordinates";
import { useAssetUrl } from "../hooks/useAssetUrl";
import { CropCanvas } from "./CropCanvas";
import { ReplaceCropDialog } from "./ReplaceCropDialog";

export function CropWorkspace({
  projectId,
  floor,
  documents,
  onClose,
  onChanged,
  onSaved,
}: {
  projectId: string;
  floor: FloorPlanFloor;
  documents: FloorPlanDocument[];
  onClose: () => void;
  onChanged: () => Promise<void> | void;
  onSaved: (result: FloorCropSaveResult) => void;
}) {
  const initialDocumentId = floor.crop?.document_id || floor.source_document_id || documents.find((item) => item.is_primary)?.id || documents[0]?.id || "";
  const [documentId, setDocumentId] = useState(initialDocumentId);
  const selectedDocument = documents.find((item) => item.id === documentId) ?? null;
  const initialPage = selectedDocument?.pages.find((item) => item.id === floor.crop?.document_page_id)
    ?? selectedDocument?.pages.find((item) => item.page_number === floor.source_page_number)
    ?? selectedDocument?.pages[0]
    ?? null;
  const [pageId, setPageId] = useState(initialPage?.id || "");
  const [rotation, setRotation] = useState<Rotation>((floor.crop?.rotation ?? floor.source_rotation ?? 0) as Rotation);
  const [rect, setRect] = useState<Rect | null>(() => initialRect(floor, rotation));
  const [tool, setTool] = useState<"crop" | "pan">("crop");
  const [zoom, setZoom] = useState(1.2);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [preparing, setPreparing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingSave, setPendingSave] = useState<FloorCropSaveInput | null>(null);

  const selectedPage = useMemo(
    () => selectedDocument?.pages.find((page) => page.id === pageId) ?? selectedDocument?.pages[0] ?? null,
    [pageId, selectedDocument]
  );
  const previewUrl = useAssetUrl(selectedPage?.preview_url);

  useEffect(() => {
    if (!selectedDocument) return;
    if (!selectedDocument.pages.some((page) => page.id === pageId)) {
      setPageId(selectedDocument.pages[0]?.id || "");
      setRect(null);
    }
  }, [pageId, selectedDocument]);

  useEffect(() => {
    setPan({ x: 0, y: 0 });
    setZoom(1.2);
  }, [pageId]);

  function changeDocument(nextDocumentId: string) {
    const nextDocument = documents.find((item) => item.id === nextDocumentId);
    setDocumentId(nextDocumentId);
    setPageId(nextDocument?.pages[0]?.id || "");
    setRotation(0);
    setRect(null);
    setError(null);
  }

  function changeRotation(next: Rotation) {
    if (rect && selectedPage?.width && selectedPage.height) {
      const original = toOriginalPageRect(rect, rotation, selectedPage.width, selectedPage.height);
      setRect(fromOriginalPageRect(original, next, selectedPage.width, selectedPage.height));
    }
    setRotation(next);
  }

  async function preparePages() {
    if (!selectedDocument) return;
    setPreparing(true);
    setError(null);
    try {
      await prepareFloorPlanDocument(projectId, selectedDocument.id);
      await onChanged();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "The page previews could not be prepared.");
    } finally {
      setPreparing(false);
    }
  }

  async function uploadSource(file: File) {
    const extension = file.name.toLowerCase().split(".").pop();
    if (!extension || !["pdf", "png", "jpg", "jpeg"].includes(extension)) {
      setError("Select a PDF, PNG or JPG file.");
      return;
    }
    setUploading(true);
    setUploadProgress(0);
    setError(null);
    try {
      const result = await uploadFloorSource(projectId, floor.id, file, setUploadProgress);
      setDocumentId(result.document.id);
      setPageId(result.document.pages[0]?.id || "");
      setRotation(0);
      setRect(null);
      await onChanged();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "The floor source could not be uploaded.");
    } finally {
      setUploading(false);
    }
  }

  async function commitSave(payload: FloorCropSaveInput) {
    setSaving(true);
    setError(null);
    try {
      const result = await saveFloorCrop(projectId, floor.id, payload);
      onSaved(result);
      onClose();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "The floor crop could not be saved.");
    } finally {
      setSaving(false);
      setPendingSave(null);
    }
  }

  async function save() {
    if (!selectedDocument || !selectedPage || !rect || !selectedPage.width || !selectedPage.height) {
      setError("Select a page and draw the floor plan crop.");
      return;
    }
    const originalRect = toOriginalPageRect(rect, rotation, selectedPage.width, selectedPage.height);
    const payload: FloorCropSaveInput = {
      document_id: selectedDocument.id,
      document_page_id: selectedPage.id,
      source_page_number: selectedPage.page_number,
      original_page_width: selectedPage.width,
      original_page_height: selectedPage.height,
      rotation,
      render_dpi: 144,
      original_rect: originalRect,
      normalized_display_rect: rect,
    };
    if (floor.crop && cropChanged(floor, payload)) {
      setPendingSave(payload);
      return;
    }
    await commitSave(payload);
  }

  useEffect(() => {
    const bodyOverflow = document.body.style.overflow;
    const bodyOverscroll = document.body.style.overscrollBehavior;
    const rootOverflow = document.documentElement.style.overflow;
    document.body.style.overflow = "hidden";
    document.body.style.overscrollBehavior = "none";
    document.documentElement.style.overflow = "hidden";

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = bodyOverflow;
      document.body.style.overscrollBehavior = bodyOverscroll;
      document.documentElement.style.overflow = rootOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[100] overflow-hidden bg-white">
      <div className="flex h-[100dvh] w-screen flex-col overflow-hidden bg-white">
        <header className="flex shrink-0 flex-wrap items-center justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Floor plan crop</p>
            <h2 className="mt-1 text-lg font-semibold text-slate-950">{floor.name}</h2>
          </div>
          <div className="flex items-center gap-2">
            <ToolButton active={tool === "crop"} onClick={() => setTool("crop")}>Crop</ToolButton>
            <ToolButton active={tool === "pan"} onClick={() => setTool("pan")}>Hand</ToolButton>
            <ToolButton onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}>Fit</ToolButton>
            <ToolButton onClick={() => setZoom(Math.max(0.25, zoom / 1.2))}>−</ToolButton>
            <span className="min-w-16 text-center text-xs font-semibold text-slate-500">{Math.round(zoom * 100)}%</span>
            <ToolButton onClick={() => setZoom(Math.min(40, zoom * 1.2))}>+</ToolButton>
            <button
              type="button"
              onClick={onClose}
              className="ml-2 inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50"
              aria-label="Close crop workspace"
            >
              ×
            </button>
          </div>
        </header>

        <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[180px_minmax(0,1fr)_300px] xl:grid-cols-[200px_minmax(0,1fr)_320px]">
          <aside className="hidden min-h-0 overflow-y-auto border-r border-slate-200 bg-slate-50 p-3 lg:block">
            <p className="px-1 pb-3 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Pages</p>
            {selectedDocument?.pages.length ? (
              <div className="space-y-3">
                {selectedDocument.pages.map((page) => (
                  <PageThumbnail
                    key={page.id}
                    page={page}
                    active={selectedPage?.id === page.id}
                    onClick={() => {
                      setPageId(page.id);
                      setRect(null);
                    }}
                  />
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-200 bg-white p-4 text-center">
                <p className="text-xs leading-5 text-slate-500">
                  {selectedDocument?.status === "failed"
                    ? "Page preparation stopped."
                    : "Page previews are being prepared."}
                </p>
                {selectedDocument ? (
                  <button
                    type="button"
                    onClick={() => void preparePages()}
                    disabled={preparing}
                    className="mt-3 text-xs font-semibold text-blue-700 hover:text-blue-800 disabled:text-slate-400"
                  >
                    {preparing ? "Preparing" : selectedDocument.status === "failed" ? "Retry preparation" : "Prepare pages"}
                  </button>
                ) : null}
              </div>
            )}
          </aside>

          <section className="min-h-0 overflow-hidden border-r border-slate-200">
            <CropCanvas
              imageUrl={previewUrl}
              rotation={rotation}
              value={rect}
              onChange={setRect}
              tool={tool}
              zoom={zoom}
              pan={pan}
              onPanChange={setPan}
              onZoomChange={setZoom}
            />
          </section>

          <aside className="min-h-0 overflow-y-auto bg-white p-5">
            <div className="space-y-6">
              <section>
                <label className="block text-sm font-semibold text-slate-700">Source file</label>
                <select
                  value={documentId}
                  onChange={(event) => changeDocument(event.target.value)}
                  className="mt-2 h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:border-blue-400"
                >
                  {documents.map((document) => (
                    <option key={document.id} value={document.id}>
                      {document.is_primary ? "Main PDF — " : ""}{document.file_name}
                    </option>
                  ))}
                </select>
                <label className="mt-3 inline-flex h-10 w-full cursor-pointer items-center justify-center rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50">
                  {uploading ? `Uploading ${uploadProgress}%` : "Upload separate file"}
                  <input
                    type="file"
                    accept="application/pdf,image/png,image/jpeg,.pdf,.png,.jpg,.jpeg"
                    className="hidden"
                    disabled={uploading}
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) void uploadSource(file);
                      event.target.value = "";
                    }}
                  />
                </label>
              </section>

              <section>
                <label className="block text-sm font-semibold text-slate-700">Page</label>
                <select
                  value={selectedPage?.id || ""}
                  onChange={(event) => {
                    setPageId(event.target.value);
                    setRect(null);
                  }}
                  className="mt-2 h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:border-blue-400"
                >
                  {selectedDocument?.pages.map((page) => (
                    <option key={page.id} value={page.id}>Page {page.page_number}{page.page_label ? ` — ${page.page_label}` : ""}</option>
                  ))}
                </select>
              </section>

              <section>
                <p className="text-sm font-semibold text-slate-700">Page rotation</p>
                <div className="mt-2 grid grid-cols-4 gap-2">
                  {([0, 90, 180, 270] as Rotation[]).map((value) => (
                    <button
                      type="button"
                      key={value}
                      onClick={() => changeRotation(value)}
                      className={rotation === value
                        ? "h-10 rounded-lg border border-blue-600 bg-blue-50 text-xs font-semibold text-blue-700"
                        : "h-10 rounded-lg border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50"}
                    >
                      {value}°
                    </button>
                  ))}
                </div>
              </section>

              <section className="rounded-xl bg-slate-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Wall height</p>
                <p className="mt-2 text-sm font-semibold text-slate-900">{Math.round(floor.effective_wall_height_mm)} mm</p>
                <p className="mt-1 text-xs text-slate-500">{floor.uses_default_height ? "Project default" : "Floor override"}</p>
              </section>

              <button
                type="button"
                onClick={() => {
                  setRect(null);
                  setZoom(1.2);
                  setPan({ x: 0, y: 0 });
                }}
                className="text-sm font-semibold text-slate-600 hover:text-slate-950"
              >
                Reset crop
              </button>

              {error ? <ErrorMessage message={error} /> : null}
            </div>
          </aside>
        </div>

        <footer className="flex shrink-0 items-center justify-between gap-4 border-t border-slate-200 px-5 py-4">
          <p className="text-xs text-slate-500">Only the drawing canvas zooms. Crop coordinates remain tied to the original page.</p>
          <div className="flex gap-3">
            <Button variant="secondary" onClick={onClose} disabled={saving}>Cancel</Button>
            <Button onClick={() => void save()} disabled={saving || !selectedPage || !rect}>
              {saving ? "Saving" : "Save crop"}
            </Button>
          </div>
        </footer>
      </div>
      {pendingSave ? (
        <ReplaceCropDialog
          floorName={floor.name}
          busy={saving}
          onCancel={() => setPendingSave(null)}
          onConfirm={() => void commitSave(pendingSave)}
        />
      ) : null}
    </div>
  );
}

function cropChanged(floor: FloorPlanFloor, payload: FloorCropSaveInput): boolean {
  const crop = floor.crop;
  if (!crop) return false;
  if (crop.document_id !== payload.document_id || crop.document_page_id !== payload.document_page_id || crop.rotation !== payload.rotation) return true;
  const previous = crop.coordinates.original_rect;
  if (!previous) return true;
  return (["x", "y", "width", "height"] as const).some((key) => Math.abs(previous[key] - payload.original_rect[key]) > 0.05);
}

function initialRect(floor: FloorPlanFloor, rotation: Rotation): Rect | null {
  const crop = floor.crop;
  if (!crop) return null;
  const original = crop.coordinates.original_rect;
  if (!original) return crop.coordinates.normalized_display_rect ?? null;
  return fromOriginalPageRect(original, rotation, crop.original_page_width, crop.original_page_height);
}

function PageThumbnail({ page, active, onClick }: { page: FloorPlanPage; active: boolean; onClick: () => void }) {
  const imageUrl = useAssetUrl(page.thumbnail_url);
  return (
    <button
      type="button"
      onClick={onClick}
      className={active
        ? "w-full overflow-hidden rounded-xl border-2 border-blue-600 bg-white p-2 text-left shadow-sm"
        : "w-full overflow-hidden rounded-xl border border-slate-200 bg-white p-2 text-left hover:border-blue-300"}
    >
      <div className="flex aspect-[4/3] items-center justify-center overflow-hidden rounded-lg bg-slate-100">
        {imageUrl ? <img src={imageUrl} alt="" className="max-h-full max-w-full object-contain" /> : <span className="text-xs text-slate-400">Preparing</span>}
      </div>
      <p className="mt-2 text-xs font-semibold text-slate-700">Page {page.page_number}</p>
    </button>
  );
}

function ToolButton({ active = false, onClick, children }: { active?: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={active
        ? "inline-flex h-10 items-center rounded-lg bg-slate-950 px-3 text-sm font-semibold text-white"
        : "inline-flex h-10 items-center rounded-lg border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-600 hover:bg-slate-50"}
    >
      {children}
    </button>
  );
}
