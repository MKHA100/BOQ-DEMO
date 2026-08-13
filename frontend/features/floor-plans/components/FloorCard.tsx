"use client";

import { useState } from "react";
import { Button } from "@/shared/components/Button";
import type { FloorPlanDocument, FloorPlanFloor } from "../types";
import { useAssetUrl } from "../hooks/useAssetUrl";

export function FloorCard({
  floor,
  documents,
  defaultHeight,
  onEdit,
  onRename,
  onHeightChange,
  onRemove,
  canRemove,
}: {
  floor: FloorPlanFloor;
  documents: FloorPlanDocument[];
  defaultHeight: number;
  onEdit: () => void;
  onRename: (name: string) => Promise<void>;
  onHeightChange: (usesDefault: boolean, height: number | null) => Promise<void>;
  onRemove: () => Promise<void>;
  canRemove: boolean;
}) {
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(floor.name);
  const [height, setHeight] = useState(String(Math.round(floor.wall_height_mm ?? defaultHeight)));
  const [busy, setBusy] = useState(false);
  const previewUrl = useAssetUrl(floor.crop?.preview_asset_url);
  const source = documents.find((document) => document.id === (floor.crop?.document_id || floor.source_document_id));

  async function saveName() {
    const clean = name.trim();
    if (!clean || clean === floor.name) {
      setName(floor.name);
      setRenaming(false);
      return;
    }
    setBusy(true);
    try {
      await onRename(clean);
      setRenaming(false);
    } finally {
      setBusy(false);
    }
  }

  async function changeHeightMode(usesDefault: boolean) {
    setBusy(true);
    try {
      await onHeightChange(usesDefault, usesDefault ? null : Number(height));
    } finally {
      setBusy(false);
    }
  }

  async function saveHeight() {
    const parsed = Number(height);
    if (!Number.isFinite(parsed) || parsed <= 0) return;
    setBusy(true);
    try {
      await onHeightChange(false, parsed);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-col gap-5 p-5 lg:flex-row lg:items-center">
        <div className="flex min-w-0 flex-1 items-center gap-4">
          <div className="flex h-28 w-40 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
            {previewUrl ? (
              <img src={previewUrl} alt={`${floor.name} crop`} className="h-full w-full object-contain" />
            ) : (
              <div className="px-4 text-center text-xs font-medium leading-5 text-slate-400">
                {floor.crop ? "Preview is processing" : "No crop saved"}
              </div>
            )}
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-3">
              {renaming ? (
                <div className="flex items-center gap-2">
                  <input
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    maxLength={80}
                    autoFocus
                    className="h-10 rounded-lg border border-blue-300 px-3 text-base font-semibold outline-none ring-4 ring-blue-50"
                  />
                  <Button disabled={busy} onClick={() => void saveName()}>Save</Button>
                  <Button variant="secondary" disabled={busy} onClick={() => { setName(floor.name); setRenaming(false); }}>Cancel</Button>
                </div>
              ) : (
                <>
                  <h3 className="truncate text-lg font-semibold text-slate-950">{floor.name}</h3>
                  <Status status={floor.status} />
                  {floor.active_jobs.length && floor.crop?.preview_asset_url ? <span className="text-xs font-medium text-blue-700">Analysis running</span> : null}
                </>
              )}
            </div>
            <p className="mt-2 truncate text-sm text-slate-500">
              {source ? `${source.file_name}${floor.crop ? ` · Page ${floor.crop.source_page_number}` : ""}` : "Select a source and crop the floor plan"}
            </p>
            <p className="mt-1 text-xs text-slate-400">
              {floor.crop ? `Crop version ${floor.crop.crop_version}` : "Not saved"}
            </p>
            {floor.last_error ? (
              <p className="mt-2 line-clamp-2 text-xs font-medium text-red-600">
                {floor.last_error}
              </p>
            ) : null}
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-[180px_160px] lg:w-[380px]">
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Wall height</span>
            <select
              value={floor.uses_default_height ? "default" : "override"}
              disabled={busy}
              onChange={(event) => void changeHeightMode(event.target.value === "default")}
              className="mt-2 h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-medium outline-none focus:border-blue-400"
            >
              <option value="default">Project default</option>
              <option value="override">Floor override</option>
            </select>
          </label>
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Height (mm)</span>
            <input
              type="number"
              min={1}
              max={30000}
              value={floor.uses_default_height ? Math.round(defaultHeight) : height}
              disabled={busy || floor.uses_default_height}
              onChange={(event) => setHeight(event.target.value)}
              onBlur={() => { if (!floor.uses_default_height) void saveHeight(); }}
              className="mt-2 h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none disabled:bg-slate-50 disabled:text-slate-400 focus:border-blue-400"
            />
          </label>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/70 px-5 py-3">
        <button type="button" onClick={() => setRenaming(true)} className="text-sm font-semibold text-slate-600 hover:text-slate-950">
          Rename
        </button>
        <div className="flex gap-2">
          {canRemove ? (
            <Button variant="danger" disabled={busy} onClick={() => void onRemove()}>Remove</Button>
          ) : null}
          <Button onClick={onEdit}>{floor.crop ? "Edit crop" : "Select and crop"}</Button>
        </div>
      </div>
    </article>
  );
}

function Status({ status }: { status: string }) {
  const normalized = ["ready", "results_available", "processing", "needs_review", "confirmed", "failed", "not_ready"].includes(status) ? status : "not_ready";
  const labels: Record<string, string> = {
    ready: "Ready",
    results_available: "Results available",
    processing: "Processing",
    needs_review: "Needs Review",
    confirmed: "Confirmed",
    failed: "Failed",
    not_ready: "Not Ready",
  };
  const styles: Record<string, string> = {
    ready: "border-emerald-200 bg-emerald-50 text-emerald-700",
    confirmed: "border-emerald-200 bg-emerald-50 text-emerald-700",
    results_available: "border-blue-200 bg-blue-50 text-blue-700",
    processing: "border-blue-200 bg-blue-50 text-blue-700",
    needs_review: "border-amber-200 bg-amber-50 text-amber-800",
    failed: "border-red-200 bg-red-50 text-red-700",
    not_ready: "border-slate-200 bg-slate-50 text-slate-600",
  };
  return <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${styles[normalized]}`}>{labels[normalized]}</span>;
}
