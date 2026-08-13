"use client";

import Image from "next/image";
import { useRef, useState, type ChangeEvent } from "react";
import { useAssetUrl } from "@/features/floor-plans/hooks/useAssetUrl";
import type { FloorOption, ScopeMode, SupportingSource } from "../types";
import { FloorScopeControl } from "./FloorScopeControl";
import { StatusPill } from "./StatusPill";

function sizeLabel(bytes: number) {
  if (!bytes) return "Project PDF crop";
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function SourceCard({
  source,
  floors,
  busy,
  onReplace,
  onEditCrop,
  onRemove,
  onScopeChange,
}: {
  source: SupportingSource;
  floors: FloorOption[];
  busy?: boolean;
  onReplace: (file: File) => void;
  onEditCrop?: () => void;
  onRemove: () => void;
  onScopeChange: (scopeMode: ScopeMode, floorIds: string[]) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const previewUrl = useAssetUrl(source.preview_url);
  const [scopeSaving, setScopeSaving] = useState(false);

  async function changeScope(scopeMode: ScopeMode, floorIds: string[]) {
    setScopeSaving(true);
    try {
      await onScopeChange(scopeMode, floorIds);
    } finally {
      setScopeSaving(false);
    }
  }

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,image/png,image/jpeg,.pdf,.png,.jpg,.jpeg"
        className="hidden"
        onChange={(event: ChangeEvent<HTMLInputElement>) => {
          const file = event.target.files?.[0];
          if (file) onReplace(file);
          event.target.value = "";
        }}
      />
      <div className="flex flex-col gap-4 lg:flex-row">
        <div className="relative flex h-32 w-full shrink-0 items-center justify-center overflow-hidden rounded-xl border border-slate-200 bg-slate-50 lg:w-44">
          {previewUrl ? <Image src={previewUrl} alt="Document preview" fill sizes="(min-width: 1024px) 176px, 100vw" unoptimized className="object-contain" /> : <span className="text-sm font-semibold text-slate-400">Document</span>}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-950">{source.file_name || "Supporting document"}</p>
              <p className="mt-1 text-xs text-slate-500">
                {source.source_type === "crop" ? `Cropped from page ${source.page_number || 1}` : sizeLabel(source.file_size)}
              </p>
            </div>
            <StatusPill status={source.status} />
          </div>
          {source.status === "processing" && source.active_job ? (
            <div className="mt-3">
              <div className="h-1.5 overflow-hidden rounded-full bg-blue-100">
                <div className="h-full rounded-full bg-blue-600 transition-all" style={{ width: `${Math.max(5, source.active_job.progress)}%` }} />
              </div>
            </div>
          ) : null}
          <div className="mt-4">
            <FloorScopeControl
              floors={floors}
              scopeMode={source.scope_mode}
              floorIds={source.floor_ids}
              disabled={busy || scopeSaving}
              onChange={(scopeMode, floorIds) => void changeScope(scopeMode, floorIds)}
            />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            {onEditCrop ? (
              <button type="button" disabled={busy} onClick={onEditCrop} className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50">
                Edit crop
              </button>
            ) : null}
            <button type="button" disabled={busy} onClick={() => inputRef.current?.click()} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:border-blue-200 hover:bg-blue-50 disabled:opacity-50">
              Replace file
            </button>
            <button type="button" disabled={busy} onClick={onRemove} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-600 hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700 disabled:opacity-50">
              Remove
            </button>
            <span className="ml-auto text-xs font-medium text-slate-500">
              {source.entry_count ? `${source.entry_count} extracted item${source.entry_count === 1 ? "" : "s"}` : source.status === "processing" ? "Preparing details" : "No extracted items"}
            </span>
          </div>
        </div>
      </div>
    </article>
  );
}
