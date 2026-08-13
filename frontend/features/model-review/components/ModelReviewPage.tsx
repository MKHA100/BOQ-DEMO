"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { DrawingCanvas } from "@/features/drawing/components/DrawingCanvas";
import { rectFromPoints } from "@/features/drawing/geometry";
import type { Point } from "@/features/drawing/types";
import { useAssetUrl } from "@/features/floor-plans/hooks/useAssetUrl";
import { WorkflowStepPage } from "@/features/workflow/components/WorkflowStepPage";
import { markCanonicalFloorChanged } from "@/features/workflow/canonicalCache";
import { Button } from "@/shared/components/Button";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import { appRoutes } from "@/shared/constants/appRoutes";
import { assignScheduleEntry, createReviewElement, getModelReviewState, updateReviewElement, updateReviewProperty } from "../api";
import { layoutElementLabels } from "../labelLayout";
import type { ElementType, LabelMode, ModelReviewState, ReviewElement } from "../types";
import { ElementInspector } from "./ElementInspector";
import { ElementList } from "./ElementList";
import { ElementOverlay } from "./ElementOverlay";
import { ModelProcessingStatus } from "./ModelProcessingStatus";

const filters = ["all", "door", "window", "wall", "needs_review"] as const;
type Filter = typeof filters[number];
const queryKey = (projectId: string, floorId: string | null) => ["model-review", projectId, floorId] as const;

const filterLabel: Record<Filter, string> = {
  all: "All",
  door: "Doors",
  window: "Windows",
  wall: "Walls",
  needs_review: "Needs Review",
};

export function ModelReviewPage({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [floorId, setFloorId] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tool, setTool] = useState<"select" | "pan" | "add">("select");
  const [addType, setAddType] = useState<ElementType>("door");
  const [labelMode, setLabelMode] = useState<LabelMode>("smart");
  const [viewZoom, setViewZoom] = useState(1);
  const [draftStart, setDraftStart] = useState<Point | null>(null);
  const [optimistic, setOptimistic] = useState<Record<string, ReviewElement["geometry"]>>({});
  const [saving, setSaving] = useState(false);
  const [editingGeometryId, setEditingGeometryId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const stateQuery = useQuery({
    queryKey: queryKey(projectId, floorId),
    queryFn: () => getModelReviewState(projectId, floorId),
    refetchInterval: (query) => {
      const data = query.state.data;
      const selectedFloor = data?.floors.find((item) => item.id === floorId);
      return selectedFloor?.active_jobs.length ? 2_000 : false;
    },
    refetchOnWindowFocus: false,
  });
  const state = stateQuery.data;

  useEffect(() => {
    if (!state?.floors.length) return;
    const stored = window.sessionStorage.getItem(`autoboq:model-review:floor:${projectId}`);
    const next = state.floors.find((floor) => floor.id === floorId)
      ?? state.floors.find((floor) => floor.id === stored)
      ?? state.floors[0];
    if (next.id !== floorId) setFloorId(next.id);
  }, [floorId, projectId, state?.floors]);

  useEffect(() => {
    if (floorId) window.sessionStorage.setItem(`autoboq:model-review:floor:${projectId}`, floorId);
  }, [floorId, projectId]);

  const floor = state?.floors.find((item) => item.id === floorId) ?? null;
  const imageUrl = useAssetUrl(floor?.drawing_url);
  const elements = useMemo(
    () => (state?.elements || []).map((element) => optimistic[element.id]
      ? { ...element, geometry: optimistic[element.id] }
      : element),
    [optimistic, state?.elements],
  );
  const visible = useMemo(() => elements.filter((element) => {
    if (filter === "all") return true;
    if (filter === "needs_review") return element.status === "needs_review";
    return element.element_type === filter;
  }), [elements, filter]);
  const selected = elements.find((element) => element.id === selectedId) ?? null;

  const placements = useMemo(() => layoutElementLabels(visible, {
    drawingWidth: floor?.drawing_width || 1,
    drawingHeight: floor?.drawing_height || 1,
    zoom: viewZoom,
    mode: labelMode,
    selectedId,
  }), [floor?.drawing_height, floor?.drawing_width, labelMode, selectedId, viewZoom, visible]);

  const renderElements = useMemo(() => [...visible].sort((a, b) => {
    if (a.id === selectedId) return 1;
    if (b.id === selectedId) return -1;
    const order = { wall: 0, window: 1, door: 2 } as const;
    return order[a.element_type] - order[b.element_type] || a.item_number - b.item_number;
  }), [selectedId, visible]);

  const onViewChange = useCallback((view: { zoom: number; pan: Point }) => {
    setViewZoom((current) => Math.abs(current - view.zoom) > 0.001 ? view.zoom : current);
  }, []);

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: queryKey(projectId, floorId), refetchType: "active" });
  }

  function updateElementCache(elementId: string, patch: Partial<ReviewElement>) {
    queryClient.setQueryData(queryKey(projectId, floorId), (current: ModelReviewState | undefined) => current ? {
      ...current,
      elements: current.elements.map((item) => item.id === elementId ? { ...item, ...patch } : item),
    } : current);
  }

  async function patchElement(element: ReviewElement, patch: Record<string, unknown>) {
    setSaving(true);
    setError(null);
    const previous = queryClient.getQueryData<ModelReviewState>(queryKey(projectId, floorId));
    updateElementCache(element.id, patch as Partial<ReviewElement>);
    try {
      const result = await updateReviewElement(projectId, element.floor_id, element.id, patch);
      updateElementCache(element.id, { ...element, ...result.record });
      markCanonicalFloorChanged(queryClient, projectId, element.floor_id, {
        elements: true,
        walls: true,
        rooms: Boolean(patch.geometry && element.element_type === "door"),
        review: true,
        boq: true,
      });
    } catch (reason) {
      if (previous) queryClient.setQueryData(queryKey(projectId, floorId), previous);
      setError(reason instanceof Error ? reason.message : "The element could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  async function finishGeometry(element: ReviewElement) {
    const geometry = optimistic[element.id];
    if (!geometry) {
      setEditingGeometryId(null);
      return;
    }
    await patchElement(element, { geometry });
    setOptimistic((current) => {
      const next = { ...current };
      delete next[element.id];
      return next;
    });
    setEditingGeometryId(null);
  }

  async function canvasClick(point: Point) {
    if (tool !== "add" || !floor) return;
    if (!draftStart) {
      setDraftStart(point);
      return;
    }
    const geometry = rectFromPoints(draftStart, point);
    setDraftStart(null);
    if (geometry.width < 3 || geometry.height < 3) {
      setError("Draw a larger element box.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const result = await createReviewElement(projectId, floor.id, { element_type: addType, geometry });
      await refresh();
      markCanonicalFloorChanged(queryClient, projectId, floor.id, { elements: true, walls: true, review: true, boq: true });
      setSelectedId(result.record.id);
      setTool("select");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The element could not be added.");
    } finally {
      setSaving(false);
    }
  }

  function chooseFloor(nextFloorId: string) {
    setFloorId(nextFloorId);
    setSelectedId(null);
    setEditingGeometryId(null);
    setOptimistic({});
    setDraftStart(null);
  }

  function chooseElement(element: ReviewElement) {
    setSelectedId(element.id);
    setEditingGeometryId(null);
    setTool("select");
  }

  return (
    <WorkflowStepPage projectId={projectId} stepKey="model-review">
      <div className="grid h-[calc(100dvh-220px)] min-h-[780px] max-h-[1240px] grid-cols-[250px_minmax(0,1fr)_310px] overflow-hidden">
        <aside className="flex min-h-0 flex-col border-r border-slate-200 bg-white p-4">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Floors</p>
          <div className="max-h-64 space-y-2 overflow-y-auto pr-1">
            {state?.floors.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => chooseFloor(item.id)}
                className={item.id === floorId
                  ? "w-full rounded-xl border border-blue-200 bg-blue-50 p-3 text-left"
                  : "w-full rounded-xl border border-slate-200 p-3 text-left hover:border-blue-200"}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-slate-900">{item.name}</span>
                  <span className="rounded-md bg-white px-1.5 py-0.5 text-xs font-semibold text-slate-600">{item.element_count}</span>
                </div>
                <div className="mt-2 flex items-center justify-between text-xs">
                  <ModelProcessingStatus floor={item} />
                  {item.needs_review_count ? <span className="text-amber-700">{item.needs_review_count} to review</span> : null}
                </div>
              </button>
            ))}
          </div>

          <div className="mt-5 border-t border-slate-200 pt-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Show</p>
            <div className="grid grid-cols-2 gap-1.5">
              {filters.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setFilter(item)}
                  className={filter === item
                    ? "rounded-lg bg-slate-950 px-2.5 py-2 text-left text-xs font-semibold text-white"
                    : "rounded-lg border border-slate-200 px-2.5 py-2 text-left text-xs font-semibold text-slate-600 hover:bg-slate-50"}
                >
                  {filterLabel[item]}
                </button>
              ))}
            </div>
          </div>

          <ElementList elements={visible} selectedId={selectedId} onSelect={chooseElement} />
        </aside>

        <main className="relative flex min-h-0 min-w-0 flex-col overflow-hidden border-r border-slate-200 bg-slate-100">
          <div className="flex min-h-14 flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-white px-4 py-2">
            <div className="flex gap-2">
              <Button variant={tool === "select" ? "primary" : "secondary"} onClick={() => { setTool("select"); setEditingGeometryId(null); }}>Select</Button>
              <Button variant={tool === "pan" ? "primary" : "secondary"} onClick={() => { setTool("pan"); setEditingGeometryId(null); }}>Hand</Button>
              <Button variant={tool === "add" ? "primary" : "secondary"} onClick={() => { setTool("add"); setEditingGeometryId(null); }}>Add element</Button>
            </div>
            <div className="flex items-center gap-2">
              {tool === "add" ? (
                <select className="input h-10 w-32" value={addType} onChange={(event) => setAddType(event.target.value as ElementType)}>
                  <option value="door">Door</option>
                  <option value="window">Window</option>
                  <option value="wall">Wall</option>
                </select>
              ) : null}
              <label className="flex items-center gap-2 text-xs font-semibold text-slate-500">
                Labels
                <select className="input h-10 w-28" value={labelMode} onChange={(event) => setLabelMode(event.target.value as LabelMode)}>
                  <option value="smart">Smart</option>
                  <option value="all">All</option>
                  <option value="selected">Selected</option>
                </select>
              </label>
            </div>
          </div>

          {floor ? (
            <DrawingCanvas
              imageUrl={imageUrl}
              width={floor.drawing_width}
              height={floor.drawing_height}
              tool={tool === "pan" ? "pan" : tool === "add" ? "draw" : "select"}
              onCanvasClick={(point) => void canvasClick(point)}
              onViewChange={onViewChange}
              className="min-h-0 flex-1"
            >
              {renderElements.map((element) => (
                <ElementOverlay
                  key={element.id}
                  element={element}
                  selected={element.id === selectedId}
                  editing={tool === "select" && editingGeometryId === element.id}
                  zoom={viewZoom}
                  label={placements.get(element.id)}
                  onSelect={() => chooseElement(element)}
                  onGeometryChange={(geometry) => setOptimistic((current) => ({ ...current, [element.id]: geometry }))}
                />
              ))}
              {draftStart ? <circle cx={draftStart.x} cy={draftStart.y} r={6} fill="#2563eb" stroke="white" strokeWidth={2} vectorEffect="non-scaling-stroke" /> : null}
            </DrawingCanvas>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-slate-500">No floor drawing is available.</div>
          )}

          {selected && optimistic[selected.id] ? (
            <div className="absolute bottom-8 left-1/2 z-20 flex -translate-x-1/2 gap-2 rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
              <Button variant="secondary" onClick={() => {
                setOptimistic((current) => {
                  const next = { ...current };
                  delete next[selected.id];
                  return next;
                });
                setEditingGeometryId(null);
              }}>Cancel</Button>
              <Button onClick={() => void finishGeometry(selected)}>Save position</Button>
            </div>
          ) : null}
        </main>

        <aside className="min-h-0 overflow-y-auto bg-white">
          <ElementInspector
            element={selected}
            schedules={state?.schedule_entries || []}
            saving={saving}
            editingGeometry={Boolean(selected && editingGeometryId === selected.id)}
            onToggleGeometryEdit={() => {
              if (!selected) return;
              setTool("select");
              setEditingGeometryId((current) => current === selected.id ? null : selected.id);
            }}
            onPatch={(patch) => selected ? patchElement(selected, patch) : Promise.resolve()}
            onProperty={async (name, value, unit) => {
              if (!selected) return;
              setSaving(true);
              try {
                await updateReviewProperty(projectId, selected.floor_id, selected.id, name, value, unit);
                markCanonicalFloorChanged(queryClient, projectId, selected.floor_id, { elements: true, walls: true, review: true, boq: true });
              } finally {
                setSaving(false);
              }
            }}
            onSchedule={async (entryId) => {
              if (!selected) return;
              setSaving(true);
              try {
                await assignScheduleEntry(projectId, selected.floor_id, selected.id, entryId);
                markCanonicalFloorChanged(queryClient, projectId, selected.floor_id, { elements: true, walls: true, review: true, boq: true });
              } finally {
                setSaving(false);
              }
            }}
          />
          {error ? <div className="px-5 pb-5"><ErrorMessage message={error} /></div> : null}
        </aside>
      </div>

      <div className="flex items-center justify-between border-t border-slate-200 bg-white px-6 py-4">
        <Link className="inline-flex h-11 items-center rounded-xl border border-slate-200 px-5 text-sm font-semibold text-slate-700 hover:bg-slate-50" href={appRoutes.workflowStep(projectId, "scale")}>Back to Scale</Link>
        <Link className="inline-flex h-11 items-center rounded-xl bg-blue-600 px-5 text-sm font-semibold text-white hover:bg-blue-700" href={appRoutes.workflowStep(projectId, "walls")}>Continue to Walls</Link>
      </div>
    </WorkflowStepPage>
  );
}
