"use client";

import Image from "next/image";
import { useEffect, useMemo, useState, type ChangeEvent } from "react";
import { CropCanvas } from "@/features/floor-plans/components/CropCanvas";
import { useAssetUrl } from "@/features/floor-plans/hooks/useAssetUrl";
import { fromOriginalPageRect, toOriginalPageRect } from "@/features/floor-plans/utils/coordinates";
import type { CropRect, DocumentOption, FloorOption, ScopeMode, SpecificationCategoryKey, SupportingSource } from "../types";
import { FloorScopeControl } from "./FloorScopeControl";

type Props = {
  category: SpecificationCategoryKey;
  initialSource?: SupportingSource;
  documents: DocumentOption[];
  floors: FloorOption[];
  onClose: () => void;
  onSave: (payload: {
    category: SpecificationCategoryKey;
    document_id: string;
    document_page_id: string;
    page_number: number;
    original_page_width: number;
    original_page_height: number;
    crop: CropRect;
    scope_mode: ScopeMode;
    floor_ids: string[];
  }) => Promise<void>;
};

function Thumbnail({ url, active, label, onClick }: { url: string | null; active: boolean; label: string; onClick: () => void }) {
  const asset = useAssetUrl(url);
  return (
    <button type="button" onClick={onClick} className={`w-full rounded-xl border p-2 text-left ${active ? "border-blue-500 bg-blue-50" : "border-slate-200 bg-white hover:border-blue-200"}`}>
      <div className="relative flex h-24 items-center justify-center overflow-hidden rounded-lg bg-slate-100">
        {asset ? <Image src={asset} alt="" fill sizes="166px" unoptimized className="object-contain" /> : <span className="text-xs text-slate-400">Loading</span>}
      </div>
      <p className="mt-2 text-xs font-semibold text-slate-600">{label}</p>
    </button>
  );
}

export function DocumentCropModal({ category, initialSource, documents, floors, onClose, onSave }: Props) {
  const firstDocument = documents.find((item) => item.id === initialSource?.document_id) || documents.find((item) => item.is_primary) || documents[0] || null;
  const [documentId, setDocumentId] = useState(firstDocument?.id || "");
  const selectedDocument = documents.find((item) => item.id === documentId) || firstDocument;
  const [pageNumber, setPageNumber] = useState(initialSource?.page_number || selectedDocument?.pages[0]?.page_number || 1);
  const page = selectedDocument?.pages.find((item) => item.page_number === pageNumber) || selectedDocument?.pages[0] || null;
  const [crop, setCrop] = useState<CropRect | null>(() => initialCrop(initialSource, page));
  const [zoom, setZoom] = useState(1.2);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [tool, setTool] = useState<"crop" | "pan">("crop");
  const [scopeMode, setScopeMode] = useState<ScopeMode>(initialSource?.scope_mode || "all");
  const [floorIds, setFloorIds] = useState<string[]>(initialSource?.floor_ids || []);
  const [saving, setSaving] = useState(false);
  const preview = useAssetUrl(page?.preview_url);
  const canSave = Boolean(page?.width && page?.height && crop);
  const title = useMemo(() => selectedDocument?.file_name || "Project PDF", [selectedDocument?.file_name]);

  useEffect(() => {
    const previousBodyOverflow = documentBodyStyle("overflow");
    const previousBodyOverscroll = documentBodyStyle("overscrollBehavior");
    const previousRootOverflow = document.documentElement.style.overflow;
    document.body.style.overflow = "hidden";
    document.body.style.overscrollBehavior = "none";
    document.documentElement.style.overflow = "hidden";

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.body.style.overscrollBehavior = previousBodyOverscroll;
      document.documentElement.style.overflow = previousRootOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

  function resetView() {
    setZoom(1.2);
    setPan({ x: 0, y: 0 });
  }

  async function save() {
    if (!page?.width || !page.height || !crop) return;
    setSaving(true);
    try {
      await onSave({
        category,
        document_id: page.document_id,
        document_page_id: page.id,
        page_number: page.page_number,
        original_page_width: page.width,
        original_page_height: page.height,
        crop: toOriginalPageRect(crop, 0, page.width, page.height),
        scope_mode: scopeMode,
        floor_ids: floorIds,
      });
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[100] overflow-hidden bg-white" role="dialog" aria-modal="true">
      <div className="flex h-[100dvh] w-screen flex-col overflow-hidden bg-white">
        <header className="flex shrink-0 flex-wrap items-center justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Schedules &amp; Specifications</p>
            <h3 className="mt-1 text-lg font-semibold text-slate-950">{initialSource ? "Edit specification crop" : "Crop from project PDF"}</h3>
            <p className="mt-1 text-sm text-slate-500">{title}</p>
          </div>
          <div className="flex items-center gap-2">
            <ToolButton active={tool === "crop"} onClick={() => setTool("crop")}>Crop</ToolButton>
            <ToolButton active={tool === "pan"} onClick={() => setTool("pan")}>Hand</ToolButton>
            <ToolButton onClick={resetView}>Fit</ToolButton>
            <ToolButton onClick={() => setZoom(Math.max(0.25, zoom / 1.2))}>−</ToolButton>
            <span className="min-w-16 text-center text-xs font-semibold text-slate-500">{Math.round(zoom * 100)}%</span>
            <ToolButton onClick={() => setZoom(Math.min(40, zoom * 1.2))}>+</ToolButton>
            <button type="button" onClick={onClose} className="ml-2 inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50" aria-label="Close crop workspace">×</button>
          </div>
        </header>

        <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[190px_minmax(0,1fr)_300px] xl:grid-cols-[210px_minmax(0,1fr)_330px]">
          <aside className="hidden min-h-0 overflow-y-auto border-r border-slate-200 bg-slate-50 p-3 lg:block">
            <select
              value={documentId}
              onChange={(event: ChangeEvent<HTMLSelectElement>) => {
                const next = documents.find((item) => item.id === event.target.value);
                setDocumentId(event.target.value);
                setPageNumber(next?.pages[0]?.page_number || 1);
                setCrop(null);
                resetView();
              }}
              className="mb-3 h-10 w-full rounded-lg border border-slate-200 bg-white px-2 text-sm"
            >
              {documents.map((item) => <option key={item.id} value={item.id}>{item.file_name}</option>)}
            </select>
            <div className="space-y-3">
              {(selectedDocument?.pages || []).map((item) => (
                <Thumbnail
                  key={item.id}
                  url={item.thumbnail_url}
                  active={item.page_number === page?.page_number}
                  label={`Page ${item.page_number}`}
                  onClick={() => {
                    setPageNumber(item.page_number);
                    setCrop(null);
                    resetView();
                  }}
                />
              ))}
            </div>
          </aside>

          <main className="min-h-0 overflow-hidden border-r border-slate-200 bg-slate-100">
            <CropCanvas imageUrl={preview} rotation={0} value={crop} onChange={setCrop} tool={tool} zoom={zoom} pan={pan} onPanChange={setPan} onZoomChange={setZoom} />
          </main>

          <aside className="min-h-0 overflow-y-auto bg-white p-5">
            <h4 className="text-sm font-semibold text-slate-950">Crop settings</h4>
            <p className="mt-2 text-xs leading-5 text-slate-500">Draw the required area on the page. Use Ctrl + wheel to zoom and the Hand tool to move the drawing.</p>
            <div className="mt-5">
              <FloorScopeControl floors={floors} scopeMode={scopeMode} floorIds={floorIds} onChange={(mode, ids) => { setScopeMode(mode); setFloorIds(ids); }} />
            </div>
          </aside>
        </div>

        <footer className="flex shrink-0 items-center justify-between gap-4 border-t border-slate-200 px-5 py-4">
          <p className="text-xs text-slate-500">Draw a crop before saving. Only the drawing canvas zooms.</p>
          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="h-11 rounded-xl border border-slate-200 px-5 text-sm font-semibold text-slate-700 hover:bg-slate-50">Cancel</button>
            <button type="button" disabled={!canSave || saving} onClick={() => void save()} className="h-11 rounded-xl bg-blue-600 px-5 text-sm font-semibold text-white hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400">
              {saving ? "Saving" : "Save crop"}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}

function initialCrop(source: SupportingSource | undefined, page: DocumentOption["pages"][number] | null): CropRect | null {
  if (!source?.crop || !page?.width || !page.height) return null;
  const raw = source.crop as Record<string, unknown>;
  const nested = raw.crop && typeof raw.crop === "object" ? raw.crop as Record<string, unknown> : raw;
  const x = Number(nested.x);
  const y = Number(nested.y);
  const width = Number(nested.width);
  const height = Number(nested.height);
  if (![x, y, width, height].every(Number.isFinite) || width <= 0 || height <= 0) return null;
  return fromOriginalPageRect({ x, y, width, height }, 0, page.width, page.height);
}

function documentBodyStyle(property: "overflow" | "overscrollBehavior") {
  return document.body.style[property];
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
