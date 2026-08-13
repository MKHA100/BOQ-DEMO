"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { DrawingCanvas } from "@/features/drawing/components/DrawingCanvas";
import type { Point } from "@/features/drawing/types";
import { useAssetUrl } from "@/features/floor-plans/hooks/useAssetUrl";
import { WorkflowStepPage } from "@/features/workflow/components/WorkflowStepPage";
import { Button } from "@/shared/components/Button";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import { appRoutes } from "@/shared/constants/appRoutes";
import {
  assignOpening,
  autoFixWalls,
  createWall,
  deleteWall,
  getWallsState,
  mergeWall,
  regenerateWalls,
  restoreWall,
  splitWall,
  updateWall,
} from "../api";
import type { Centerline, WallPatch } from "../types";
import { WallInspector } from "./WallInspector";
import { WallOverlay } from "./WallOverlay";

const key = (projectId: string, floorId: string | null) => ["walls", projectId, floorId] as const;
type WallTool = "select" | "pan" | "edit" | "add";

export function WallsPage({ projectId }: { projectId: string }) {
  const client = useQueryClient();
  const autoRequestedRef = useRef(new Set<string>());
  const [floorId, setFloorId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tool, setTool] = useState<WallTool>("select");
  const [addStart, setAddStart] = useState<Point | null>(null);
  const [draftLines, setDraftLines] = useState<Record<string, Centerline>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showIssues, setShowIssues] = useState(false);

  const query = useQuery({
    queryKey: key(projectId, floorId),
    queryFn: () => getWallsState(projectId, floorId),
    refetchOnWindowFocus: true,
    refetchOnMount: "always",
    staleTime: 0,
    placeholderData: (previous) => previous,
    refetchInterval: (result) => {
      const data = result.state.data;
      const selectedFloor = data?.floors.find((item) => item.id === floorId)
        || data?.floors.find((item) => item.id === data.selected_floor_id)
        || data?.floors[0];
      if (selectedFloor?.active_jobs.length) return 1500;
      if (selectedFloor?.scale_version && !data?.walls.length) return 3500;
      return false;
    },
  });
  const state = query.data;

  useEffect(() => {
    if (!state?.floors.length) return;
    const next = state.floors.find((item) => item.id === floorId) || state.floors[0];
    if (next.id !== floorId) setFloorId(next.id);
  }, [floorId, state?.floors]);

  useEffect(() => {
    setSelectedId(null);
    setDraftLines({});
    setAddStart(null);
    setTool("select");
    setShowIssues(false);
  }, [floorId]);

  const floor = state?.floors.find((item) => item.id === floorId) || null;
  const imageUrl = useAssetUrl(floor?.drawing_url);
  const walls = useMemo(
    () => (state?.walls || []).map((wall) => draftLines[wall.id] ? { ...wall, centerline: draftLines[wall.id] } : wall),
    [draftLines, state?.walls],
  );
  const selected = walls.find((wall) => wall.id === selectedId) || null;
  const processing = Boolean(floor?.active_jobs.length);
  const blockingCount = state?.validation?.blocking_issues || 0;
  const systemChecked = walls.length > 0
    && blockingCount === 0
    && walls.every((wall) => wall.status === "confirmed" || wall.user_confirmed);

  async function refresh() {
    await Promise.all([
      client.invalidateQueries({ queryKey: ["walls", projectId], refetchType: "active" }),
      client.invalidateQueries({ queryKey: ["workflow", projectId, "summary"], refetchType: "active" }),
    ]);
  }

  async function act(action: () => Promise<unknown>) {
    setSaving(true);
    setError(null);
    try {
      await action();
      await refresh();
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The wall operation could not be completed.");
      return false;
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    if (!floorId || !floor || saving || processing || walls.length || !floor.scale_version) return;
    if (state?.selected_floor_id && state.selected_floor_id !== floorId) return;
    const requestKey = `${floorId}:${floor.element_version}:${floor.wall_version}`;
    if (autoRequestedRef.current.has(requestKey)) return;
    autoRequestedRef.current.add(requestKey);
    void act(() => regenerateWalls(projectId, floorId));
    // This one-time recovery also handles old projects where model analysis completed before automatic wall jobs existed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [floor?.element_version, floor?.scale_version, floor?.wall_version, floorId, processing, projectId, saving, state?.selected_floor_id, walls.length]);

  async function save(patch: WallPatch) {
    if (!selected || !floorId) return;
    const centerline = draftLines[selected.id];
    const completed = await act(() => updateWall(projectId, floorId, selected.id, centerline ? { ...patch, centerline } : patch));
    if (completed) {
      setDraftLines((current) => {
        const next = { ...current };
        delete next[selected.id];
        return next;
      });
    }
  }

  async function addWallPoint(point: Point) {
    if (tool !== "add" || !floorId || saving) return;
    if (!addStart) {
      setAddStart(point);
      return;
    }
    if (Math.hypot(point.x - addStart.x, point.y - addStart.y) < 2) {
      setError("The wall is too short. Choose an end point farther from the start point.");
      return;
    }
    const completed = await act(() => createWall(projectId, floorId, { centerline: { start: addStart, end: point } }));
    if (completed) {
      setAddStart(null);
      setTool("select");
    }
  }

  function selectTool(next: WallTool) {
    setTool(next);
    if (next !== "add") setAddStart(null);
  }

  return (
    <WorkflowStepPage projectId={projectId} stepKey="walls">
      <div className="grid h-[calc(100dvh-286px)] min-h-[720px] max-h-[1100px] grid-cols-[220px_minmax(0,1fr)_300px] overflow-hidden">
        <aside className="flex min-h-0 flex-col overflow-hidden border-r border-slate-200 bg-white p-4">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Floors</p>
          <div className="space-y-2">
            {state?.floors.map((item) => {
              const isSelected = item.id === floorId;
              const floorLabel = item.active_jobs.length
                ? "Processing walls"
                : isSelected && walls.length
                  ? systemChecked ? "System checked" : blockingCount ? `${blockingCount} issue${blockingCount === 1 ? "" : "s"}` : "Processing checks"
                  : item.wall_status?.replaceAll("_", " ") || (item.scale_version ? "Waiting for walls" : "Needs scale");
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setFloorId(item.id)}
                  className={isSelected ? "w-full rounded-xl border border-blue-200 bg-blue-50 p-3 text-left" : "w-full rounded-xl border border-slate-200 p-3 text-left hover:border-blue-200"}
                >
                  <div className="flex justify-between"><span className="text-sm font-semibold">{item.name}</span><span className="text-xs text-slate-500">v{item.wall_version}</span></div>
                  <p className="mt-2 text-xs capitalize text-slate-500">{floorLabel}</p>
                </button>
              );
            })}
          </div>
          <div className="mt-5 flex min-h-0 flex-1 flex-col border-t border-slate-200 pt-4">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Wall items</p>
              <span className="text-xs text-slate-500">{walls.length}</span>
            </div>
            <div className="min-h-0 flex-1 space-y-1 overflow-y-auto pr-1">
              {walls.map((wall) => {
                const wallWarnings = (wall.validation_warnings || []).filter(
                  (warning) => typeof warning !== "string" && warning.severity === "error",
                ).length;
                return (
                  <button
                    key={wall.id}
                    type="button"
                    onClick={() => setSelectedId(wall.id)}
                    className={wall.id === selectedId ? "w-full rounded-lg border border-blue-300 bg-blue-50 px-3 py-2 text-left" : "w-full rounded-lg border border-transparent px-3 py-2 text-left hover:border-slate-200 hover:bg-slate-50"}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-slate-900">{wall.display_number}</span>
                      <span className={wallWarnings ? "text-[10px] font-semibold text-amber-700" : "text-[10px] font-semibold capitalize text-slate-500"}>
                        {wallWarnings ? `${wallWarnings} warning${wallWarnings === 1 ? "" : "s"}` : wall.classification || "Unclassified"}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center justify-between gap-2 text-xs text-slate-500">
                      <span className="truncate">{wall.wall_type || "Wall type not set"}</span>
                      <span className="shrink-0">{wall.length_mm ? `${(wall.length_mm / 1000).toFixed(2)} m` : "—"}</span>
                    </div>
                  </button>
                );
              })}
              {!walls.length ? (
                <p className="rounded-lg bg-slate-50 px-3 py-4 text-center text-xs text-slate-500">
                  {processing || saving ? "Generating and connecting walls…" : floor?.scale_version ? "Preparing wall items…" : "Scale this floor before generating walls."}
                </p>
              ) : null}
            </div>
          </div>
        </aside>

        <main className="relative flex min-h-0 min-w-0 flex-col overflow-hidden border-r border-slate-200 bg-slate-100">
          <div className="flex min-h-14 flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-white px-4 py-2">
            <div className="flex items-center gap-2">
              <Button variant={tool === "select" ? "primary" : "secondary"} onClick={() => selectTool("select")}>Select</Button>
              <Button variant={tool === "pan" ? "primary" : "secondary"} onClick={() => selectTool("pan")}>Hand</Button>
              <Button variant={tool === "add" ? "primary" : "secondary"} disabled={!floor || saving} onClick={() => selectTool("add")}>Add wall</Button>
              <Button variant={tool === "edit" ? "primary" : "secondary"} disabled={!selected} onClick={() => selectTool("edit")}>Edit centerline</Button>
            </div>
            <div className="flex items-center gap-2">
              {blockingCount ? <Button variant="secondary" onClick={() => setShowIssues((value) => !value)}>{showIssues ? "Hide issues" : `Show ${blockingCount} issue${blockingCount === 1 ? "" : "s"}`}</Button> : null}
              <Button variant="secondary" disabled={!floorId || !walls.length || saving || processing} onClick={() => floorId && void act(() => autoFixWalls(projectId, floorId))}>Automatic repair</Button>
              <Button
                variant="secondary"
                disabled={!floorId || saving || processing}
                onClick={() => {
                  if (floorId && window.confirm("Regenerate detected walls for this floor? Manual walls and manual edits will be preserved.")) {
                    void act(() => regenerateWalls(projectId, floorId));
                  }
                }}
              >
                Regenerate
              </Button>
              <Button disabled>{systemChecked ? "System checked" : "Checking walls"}</Button>
            </div>
          </div>

          {floor ? (
            <DrawingCanvas
              imageUrl={imageUrl}
              width={floor.drawing_width}
              height={floor.drawing_height}
              tool={tool === "pan" ? "pan" : tool === "add" ? "draw" : "select"}
              onCanvasClick={(point) => void addWallPoint(point)}
              className="min-h-0 flex-1"
            >
              {walls.map((wall) => (
                <WallOverlay
                  key={wall.id}
                  wall={wall}
                  selected={wall.id === selectedId}
                  edit={tool === "edit" && wall.id === selectedId}
                  showIssues={showIssues}
                  mmPerPixel={floor.mm_per_pixel}
                  snapPoints={walls.filter((item) => item.id !== wall.id).flatMap((item) => [item.centerline.start, item.centerline.end])}
                  onSelect={() => setSelectedId(wall.id)}
                  onChange={(line) => setDraftLines((current) => ({ ...current, [wall.id]: line }))}
                />
              ))}
              {addStart ? (
                <g pointerEvents="none">
                  <circle cx={addStart.x} cy={addStart.y} r={7} fill="#2563eb" stroke="white" strokeWidth={2} vectorEffect="non-scaling-stroke" />
                  <circle cx={addStart.x} cy={addStart.y} r={14} fill="none" stroke="#2563eb" strokeWidth={2} strokeDasharray="4 3" vectorEffect="non-scaling-stroke" />
                </g>
              ) : null}
            </DrawingCanvas>
          ) : <div className="flex h-full items-center justify-center text-sm text-slate-500">No floor drawing is ready.</div>}

          {tool === "add" ? (
            <div className="pointer-events-none absolute left-1/2 top-20 z-20 -translate-x-1/2 rounded-full bg-blue-700 px-4 py-2 text-xs font-semibold text-white shadow-lg">
              {addStart ? "Click the wall end point" : "Click the wall start point"}
            </div>
          ) : null}
          {processing ? <div className="absolute bottom-8 left-5 z-20 rounded-full bg-white px-3 py-2 text-xs font-semibold text-blue-700 shadow">Straightening and connecting walls…</div> : null}
          {selected && draftLines[selected.id] ? (
            <div className="absolute bottom-8 left-1/2 z-20 flex -translate-x-1/2 gap-2 rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
              <Button variant="secondary" onClick={() => setDraftLines((current) => { const next = { ...current }; delete next[selected.id]; return next; })}>Cancel</Button>
              <Button disabled={saving} onClick={() => void save({})}>Save centerline</Button>
            </div>
          ) : null}
        </main>

        <aside className="min-h-0 overflow-y-auto bg-white">
          {showIssues && state?.validation && !state.validation.is_valid ? (
            <div className="m-5 mb-0 rounded-xl border border-amber-200 bg-amber-50 p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-800">Floor validation</p>
              <p className="mt-1 text-xs text-amber-900">{state.validation.blocking_issues} geometry issue{state.validation.blocking_issues === 1 ? "" : "s"} remains after automatic repair.</p>
              {state.validation.warnings.length ? (
                <ul className="mt-2 space-y-1 text-xs text-amber-900">
                  {state.validation.warnings.filter((warning) => typeof warning !== "string" && warning.severity === "error").slice(0, 4).map((warning, index) => <li key={index}>• {typeof warning === "string" ? warning : warning.message}</li>)}
                </ul>
              ) : null}
            </div>
          ) : null}
          <WallInspector
            wall={selected}
            openings={state?.openings || []}
            walls={walls}
            saving={saving}
            onSave={save}
            onAssign={async (elementId) => { if (selected && floorId) await act(() => assignOpening(projectId, floorId, selected.id, elementId)); }}
            onSplit={async () => { if (selected && floorId) await act(() => splitWall(projectId, floorId, selected.id)); }}
            onMerge={async (otherId) => { if (selected && floorId) await act(() => mergeWall(projectId, floorId, selected.id, otherId)); }}
            onRestore={async () => { if (selected && floorId) await act(() => restoreWall(projectId, floorId, selected.id)); }}
            onDelete={async () => {
              if (!selected || !floorId) return;
              const completed = await act(() => deleteWall(projectId, floorId, selected.id));
              if (completed) {
                setSelectedId(null);
                setTool("select");
              }
            }}
          />
          {error ? <div className="px-5 pb-5"><ErrorMessage message={error} /></div> : null}
        </aside>
      </div>
      <div className="flex items-center justify-between border-t border-slate-200 bg-white px-6 py-4">
        <Link className="inline-flex h-11 items-center rounded-xl border border-slate-200 px-5 text-sm font-semibold text-slate-700" href={appRoutes.workflowStep(projectId, "model-review")}>Back to Model Review</Link>
        <Link className="inline-flex h-11 items-center rounded-xl bg-blue-600 px-5 text-sm font-semibold text-white" href={appRoutes.workflowStep(projectId, "floors")}>Continue to Floors</Link>
      </div>
    </WorkflowStepPage>
  );
}
