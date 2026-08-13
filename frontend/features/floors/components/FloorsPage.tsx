"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { DrawingCanvas } from "@/features/drawing/components/DrawingCanvas";
import type { Point } from "@/features/drawing/types";
import { useAssetUrl } from "@/features/floor-plans/hooks/useAssetUrl";
import { WorkflowStepPage } from "@/features/workflow/components/WorkflowStepPage";
import { Button } from "@/shared/components/Button";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import { appRoutes } from "@/shared/constants/appRoutes";
import {
  acceptRoomSuggestion,
  confirmRoom,
  correctRoomSuggestionWithWalls,
  createFinishZone,
  createRoom,
  createRoomCutout,
  deleteRoom,
  deleteRoomCutout,
  excludeRoom,
  getFloorsState,
  getRoomRevisions,
  makeRoomRectangle,
  mergeRoom,
  patchRoomGeometry,
  previewAutoFixRoom,
  rejectRoomSuggestion,
  resetRoomToCorrected,
  resetRoomToModel,
  restoreRoom,
  restoreRoomRevision,
  simplifyRoomGeometry,
  snapRoomToWalls,
  splitRoomWithLine,
  straightenRoomGeometry,
  updateRoom,
} from "../api";
import { boundingDimensions, polygonArea, polygonPerimeter } from "../geometry/editorGeometry";
import { useRoomAnalysis } from "../hooks/useRoomAnalysis";
import { useRoomEditor } from "../hooks/useRoomEditor";
import { useRoomKeyboardShortcuts } from "../hooks/useRoomKeyboardShortcuts";
import { useFloorEditorStore, type FloorEditorTool } from "../store/useFloorEditorStore";
import type { AutoFixPreview, RoomPatch } from "../types";
import { FinishZoneTool } from "./FinishZoneTool";
import { RoomCutoutTool } from "./RoomCutoutTool";
import { RoomEdgeEditor } from "./RoomEdgeEditor";
import { RoomInspector } from "./RoomInspector";
import { RoomList, type RoomFilter } from "./RoomList";
import { RoomOverlay } from "./RoomOverlay";
import { RoomSplitTool } from "./RoomSplitTool";
import { RoomSuggestionOverlay } from "./RoomSuggestionOverlay";
import { RoomToolbar } from "./RoomToolbar";
import { RoomAutoFixPreviewDialog } from "./RoomAutoFixPreviewDialog";
import { RoomVertexEditor } from "./RoomVertexEditor";

const key = (projectId: string, floorId: string | null) => ["floors", projectId, floorId] as const;
const EMPTY_POINTS: Point[] = [];
const editTools: FloorEditorTool[] = ["edit_vertex", "add_vertex", "delete_vertex", "move_edge"];

export function FloorsPage({ projectId }: { projectId: string }) {
  const client = useQueryClient();
  const persistedFloor = useFloorEditorStore((state) => state.floorByProject[projectId] || null);
  const persistedRoom = useFloorEditorStore((state) => state.roomByProject[projectId] || null);
  const setPersistedFloor = useFloorEditorStore((state) => state.setFloor);
  const setPersistedRoom = useFloorEditorStore((state) => state.setRoom);
  const setPersistedView = useFloorEditorStore((state) => state.setView);
  const storedTool = useFloorEditorStore((state) => state.tool);
  const setStoredTool = useFloorEditorStore((state) => state.setTool);

  const [floorId, setFloorId] = useState<string | null>(persistedFloor);
  const storedView = useFloorEditorStore((state) => floorId ? state.viewByFloor[floorId] : undefined);
  const [selectedId, setSelectedId] = useState<string | null>(persistedRoom);
  const [selectedSuggestionId, setSelectedSuggestionId] = useState<string | null>(null);
  const [filter, setFilter] = useState<RoomFilter>("all");
  const [tool, setToolState] = useState<FloorEditorTool>(storedTool || "select");
  const [newPoints, setNewPoints] = useState<Point[]>([]);
  const [saving, setSaving] = useState(false);
  const [autoFixLoading, setAutoFixLoading] = useState(false);
  const [autoFixPreview, setAutoFixPreview] = useState<AutoFixPreview | null>(null);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: key(projectId, floorId),
    queryFn: () => getFloorsState(projectId, floorId),
    refetchOnWindowFocus: false,
    refetchOnMount: "always",
    staleTime: 0,
    gcTime: 2 * 60 * 60_000,
    placeholderData: (previous) => previous,
    refetchInterval: (result) => result.state.data?.floors.find((floor) => floor.id === floorId)?.active_jobs.length ? 2000 : false,
  });
  const state = query.data;

  useEffect(() => {
    if (!state?.floors.length) return;
    const next = state.floors.find((floor) => floor.id === floorId) || state.floors[0];
    if (next.id !== floorId) {
      setFloorId(next.id);
      setPersistedFloor(projectId, next.id);
    }
  }, [floorId, projectId, setPersistedFloor, state?.floors]);

  const floor = state?.floors.find((item) => item.id === floorId) || null;
  const imageUrl = useAssetUrl(floor?.drawing_url);
  const sourceRooms = state?.rooms || [];
  const selectedSource = sourceRooms.find((room) => room.id === selectedId) || null;
  const editor = useRoomEditor(
    selectedSource?.id || null,
    selectedSource?.display_polygon?.points?.length ? selectedSource.display_polygon.points : selectedSource?.geometry.points || EMPTY_POINTS,
    selectedSource?.geometry_version || 0,
  );
  const editing = Boolean(selectedSource && editTools.includes(tool));
  const rooms = useMemo(() => sourceRooms.map((room) => room.id === selectedId && editing ? { ...room, geometry: { points: editor.points }, display_polygon: { points: editor.points }, point_count: editor.points.length } : room), [editing, editor.points, selectedId, sourceRooms]);
  const selected = rooms.find((room) => room.id === selectedId) || null;
  const selectedSuggestion = (state?.suggestions || []).find((item) => item.id === selectedSuggestionId) || null;
  const pendingSuggestions = (state?.suggestions || []).filter((item) => item.status === "new");
  const analysis = useRoomAnalysis(projectId, floorId);
  const revisionsQuery = useQuery({
    queryKey: ["floors", projectId, floorId, selectedId, "revisions"],
    queryFn: () => getRoomRevisions(projectId, floorId!, selectedId!),
    enabled: Boolean(floorId && selectedId),
    staleTime: 30_000,
  });

  const setTool = useCallback((next: FloorEditorTool) => {
    if (!selectedId && editTools.includes(next)) return;
    setToolState((current) => current === next ? current : next);
    setStoredTool(next);
    if (["draw_room", "split", "cutout", "zone"].includes(next)) setNewPoints([]);
  }, [selectedId, setStoredTool]);

  const handleViewChange = useCallback((view: { zoom: number; pan: Point }) => {
    if (!floorId) return;
    setPersistedView(floorId, view);
  }, [floorId, setPersistedView]);

  function refresh() {
    void client.invalidateQueries({ queryKey: key(projectId, floorId), refetchType: "active" });
    void client.invalidateQueries({ queryKey: ["workflow", projectId, "summary"], refetchType: "active" });
  }

  async function act(action: () => Promise<unknown>, optimistic?: (current: typeof state) => typeof state) {
    setSaving(true);
    setError(null);
    if (optimistic) client.setQueryData(key(projectId, floorId), optimistic);
    try {
      await action();
      refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The room could not be updated.");
      refresh();
    } finally {
      setSaving(false);
    }
  }

  async function saveDetails(patch: RoomPatch) {
    if (!selectedSource || !floorId) return;
    await act(() => updateRoom(projectId, floorId, selectedSource.id, patch), (current) => current ? {
      ...current,
      rooms: current.rooms.map((room) => room.id === selectedSource.id ? {
        ...room,
        name: patch.name !== undefined ? patch.name : room.name,
        room_type: patch.room_type !== undefined ? patch.room_type : room.room_type,
        floor_type_code: patch.floor_type_code !== undefined ? patch.floor_type_code : room.floor_type_code,
        floor_finish: patch.floor_finish !== undefined ? patch.floor_finish : room.floor_finish,
        space_kind: patch.space_kind || room.space_kind,
        include_in_boq: patch.include_in_boq !== undefined ? patch.include_in_boq : room.include_in_boq,
        open_plan: patch.open_plan !== undefined ? patch.open_plan : room.open_plan,
        status: patch.review_status || room.status,
      } : room),
    } : current);
  }

  const saveGeometry = useCallback(async () => {
    if (!selectedSource || !floorId || !editor.dirty) return;
    await act(() => patchRoomGeometry(projectId, floorId, selectedSource.id, { action: "replace", points: editor.points }));
    editor.reset();
    setTool("select");
  }, [editor, floorId, projectId, selectedSource, setTool]);

  const cancelGeometry = useCallback(() => {
    editor.reset();
    setTool("select");
  }, [editor, setTool]);

  useRoomKeyboardShortcuts({
    enabled: editing,
    onDelete: () => {
      if (editor.selectedVertex != null) editor.removeVertex(editor.selectedVertex);
    },
    onUndo: editor.undo,
    onRedo: editor.redo,
    onSave: () => void saveGeometry(),
    onCancel: cancelGeometry,
  });

  function canvasClick(point: Point) {
    if (["draw_room", "zone", "cutout"].includes(tool)) setNewPoints((current) => [...current, point]);
    if (tool === "split") {
      setNewPoints((current) => {
        const next = [...current, point];
        if (next.length === 2 && selectedSource && floorId) {
          void act(() => splitRoomWithLine(projectId, floorId, selectedSource.id, next)).then(() => {
            setNewPoints([]);
            setTool("select");
          });
        }
        return next;
      });
    }
  }

  async function finishDraw() {
    if (!floorId || newPoints.length < 3) {
      setError("Select at least three points.");
      return;
    }
    if (tool === "zone") {
      if (!selectedSource) { setError("Select the open-plan room first."); return; }
      await act(() => createFinishZone(projectId, floorId, selectedSource.id, { points: newPoints }));
    } else if (tool === "cutout") {
      if (!selectedSource) { setError("Select the room first."); return; }
      await act(() => createRoomCutout(projectId, floorId, selectedSource.id, newPoints));
    } else {
      await act(() => createRoom(projectId, floorId, { points: newPoints }));
    }
    setNewPoints([]);
    setTool("select");
  }

  function selectRoom(roomId: string) {
    setSelectedId(roomId);
    setPersistedRoom(projectId, roomId);
    setSelectedSuggestionId(null);
    if (tool === "draw_room") setTool("select");
  }

  async function requestAutoFixPreview() {
    if (!selectedSource || !floorId || autoFixLoading) return;
    setAutoFixLoading(true);
    setError(null);
    try {
      setAutoFixPreview(await previewAutoFixRoom(projectId, floorId, selectedSource.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The room could not be auto-fixed.");
    } finally {
      setAutoFixLoading(false);
    }
  }

  function applyAutoFixPreview() {
    if (!autoFixPreview) return;
    editor.replace(autoFixPreview.proposed.points);
    setAutoFixPreview(null);
    setTool("edit_vertex");
  }

  const liveMetrics = useMemo(() => {
    if (!editing || !floor?.mm_per_pixel) return null;
    const mm = floor.mm_per_pixel;
    const dimensions = boundingDimensions(editor.points);
    return {
      area: polygonArea(editor.points) * mm * mm / 1_000_000,
      perimeter: polygonPerimeter(editor.points) * mm / 1000,
      width: dimensions.width * mm / 1000,
      length: dimensions.length * mm / 1000,
    };
  }, [editing, editor.points, floor?.mm_per_pixel]);

  return (
    <WorkflowStepPage projectId={projectId} stepKey="floors">
      <div className="grid h-[calc(100dvh-286px)] min-h-[720px] max-h-[1100px] grid-cols-[230px_minmax(0,1fr)_320px] overflow-hidden">
        <RoomList
          floors={state?.floors || []}
          floorId={floorId}
          rooms={rooms}
          filter={filter}
          selectedId={selectedId}
          onFloor={(value) => {
            setFloorId(value);
            setPersistedFloor(projectId, value);
            setSelectedId(null);
            setPersistedRoom(projectId, null);
            setSelectedSuggestionId(null);
            setShowSuggestions(false);
            setTool("select");
          }}
          onFilter={setFilter}
          onSelect={selectRoom}
        />

        <main className="relative flex min-h-0 min-w-0 flex-col overflow-hidden border-r border-slate-200 bg-slate-100">
          <RoomToolbar
            processing={Boolean(floor?.active_jobs.length) || analysis.running}
            hasRooms={rooms.some((room) => !room.excluded)}
            hasSelection={Boolean(selected)}
            autoFixing={autoFixLoading}
            tool={tool}
            editing={editing}
            canUndo={editor.canUndo}
            canRedo={editor.canRedo}
            onTool={setTool}
            onAnalyze={() => void analysis.analyze()}
            onRecalculate={() => void analysis.recalculate()}
            onConfirmAll={() => void analysis.confirmAll()}
            onAutoFix={() => void requestAutoFixPreview()}
            onSimplify={() => editing ? editor.simplify() : selectedSource && floorId ? void act(() => simplifyRoomGeometry(projectId, floorId, selectedSource.id)) : undefined}
            onRectangle={() => editing ? editor.rectangle() : selectedSource && floorId ? void act(() => makeRoomRectangle(projectId, floorId, selectedSource.id)) : undefined}
            onStraighten={() => editing ? editor.straighten() : selectedSource && floorId ? void act(() => straightenRoomGeometry(projectId, floorId, selectedSource.id)) : undefined}
            onSnap={() => selectedSource && floorId ? void act(() => snapRoomToWalls(projectId, floorId, selectedSource.id)) : undefined}
            onUndo={editor.undo}
            onRedo={editor.redo}
            onSave={() => void saveGeometry()}
            onCancel={cancelGeometry}
          />

          {floor ? (
            <DrawingCanvas
              key={floor.id}
              imageUrl={imageUrl}
              width={floor.drawing_width}
              height={floor.drawing_height}
              tool={tool === "pan" ? "pan" : ["draw_room", "split", "zone", "cutout"].includes(tool) ? "draw" : "select"}
              onCanvasClick={canvasClick}
              initialView={storedView}
              onViewChange={handleViewChange}
              className="min-h-0 flex-1"
            >
              {rooms.map((room) => (
                <RoomOverlay key={room.id} room={room} selected={room.id === selectedId} onSelect={() => selectRoom(room.id)} />
              ))}
              {editing && selected ? (
                <>
                  <RoomEdgeEditor
                    points={editor.points}
                    mode={tool === "add_vertex" ? "add" : tool === "move_edge" ? "move" : "select"}
                    selectedIndex={editor.selectedEdge}
                    onSelect={editor.selectEdge}
                    onAddPoint={(index, point) => { editor.addVertex(index, point); setTool("edit_vertex"); }}
                    onMove={editor.shiftEdge}
                  />
                  <RoomVertexEditor
                    points={editor.points}
                    selectedIndex={editor.selectedVertex}
                    onSelect={(index) => {
                      if (tool === "delete_vertex") editor.removeVertex(index);
                      else editor.selectVertex(index);
                    }}
                    onMove={editor.updateVertex}
                  />
                </>
              ) : null}
              {(showSuggestions ? pendingSuggestions : []).map((suggestion) => (
                <RoomSuggestionOverlay
                  key={suggestion.id}
                  suggestion={suggestion}
                  selected={suggestion.id === selectedSuggestionId}
                  onSelect={() => { setSelectedSuggestionId(suggestion.id); setSelectedId(null); setPersistedRoom(projectId, null); }}
                />
              ))}
              {newPoints.length ? (
                <>
                  <polyline points={newPoints.map((point) => `${point.x},${point.y}`).join(" ")} fill={newPoints.length >= 3 ? "rgba(37,99,235,.08)" : "none"} stroke="#2563eb" strokeWidth={2} vectorEffect="non-scaling-stroke" />
                  {newPoints.map((point, index) => <circle key={index} cx={point.x} cy={point.y} r={4} fill="#2563eb" stroke="white" strokeWidth={2} vectorEffect="non-scaling-stroke" />)}
                </>
              ) : null}
            </DrawingCanvas>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-slate-500">No floor drawing is ready.</div>
          )}

          {pendingSuggestions.length && !editing ? (
            <div className="absolute right-4 top-20 z-20">
              <Button variant="secondary" onClick={() => {
                setShowSuggestions((value) => !value);
                if (showSuggestions) setSelectedSuggestionId(null);
              }}>
                {showSuggestions ? "Hide suggestions" : `Review ${pendingSuggestions.length} possible missing`}
              </Button>
            </div>
          ) : null}

          {["draw_room", "zone", "cutout", "split"].includes(tool) ? (
            <div className="absolute bottom-8 left-1/2 z-20 flex -translate-x-1/2 items-center gap-2 rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
              <Button variant="secondary" onClick={() => { setNewPoints([]); setTool("select"); }}>Cancel</Button>
              {tool === "split" ? <RoomSplitTool /> : tool === "cutout" ? <RoomCutoutTool /> : tool === "zone" ? <FinishZoneTool /> : null}
              {tool !== "split" ? <Button disabled={newPoints.length < 3} onClick={() => void finishDraw()}>{tool === "zone" ? "Save zone" : tool === "cutout" ? "Save cutout" : "Save room"}</Button> : null}
            </div>
          ) : null}
          {editing && liveMetrics ? (
            <div className="absolute bottom-4 right-4 z-20 rounded-xl border border-slate-200 bg-white/95 px-4 py-3 text-xs shadow-lg backdrop-blur">
              <div className="font-semibold text-slate-800">Live measurement</div>
              <div className="mt-1 text-slate-600">{liveMetrics.area.toFixed(2)} m² · {liveMetrics.perimeter.toFixed(2)} m</div>
              <div className="text-slate-600">{liveMetrics.width.toFixed(2)} × {liveMetrics.length.toFixed(2)} m</div>
            </div>
          ) : null}
        </main>

        <aside className="min-h-0 overflow-y-auto bg-white">
          {selectedSuggestion && floorId ? (
            <div className="space-y-5 p-5">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[.14em] text-slate-400">Room suggestion</p>
                <h3 className="mt-1 text-lg font-semibold">Possible missing room</h3>
                <p className="mt-1 text-sm text-slate-500">Check the dashed boundary, then accept or reject it.</p>
              </div>
              <div className="space-y-2">
                <Button className="w-full" onClick={() => void act(() => correctRoomSuggestionWithWalls(projectId, floorId, selectedSuggestion.id))}>Correct with walls</Button>
                <div className="grid grid-cols-2 gap-2">
                  <Button variant="secondary" onClick={() => void act(() => acceptRoomSuggestion(projectId, floorId, selectedSuggestion.id))}>Use model shape</Button>
                  <Button variant="secondary" onClick={() => void act(() => rejectRoomSuggestion(projectId, floorId, selectedSuggestion.id))}>Reject</Button>
                </div>
              </div>
            </div>
          ) : (
            <RoomInspector
              room={selected}
              rooms={rooms}
              saving={saving}
              revisions={revisionsQuery.data?.items || []}
              onSave={saveDetails}
              onEdit={() => setTool("edit_vertex")}
              onConfirm={() => selectedSource && floorId ? act(() => confirmRoom(projectId, floorId, selectedSource.id)) : Promise.resolve()}
              onExclude={() => selectedSource && floorId ? act(() => excludeRoom(projectId, floorId, selectedSource.id)) : Promise.resolve()}
              onDelete={() => selectedSource && floorId ? act(() => deleteRoom(projectId, floorId, selectedSource.id)) : Promise.resolve()}
              onSplitLine={() => { if (selectedSource) setTool("split"); }}
              onAddZone={() => { if (selectedSource) setTool("zone"); }}
              onAddCutout={() => { if (selectedSource) setTool("cutout"); }}
              onMerge={(roomId) => selectedSource && floorId ? act(() => mergeRoom(projectId, floorId, selectedSource.id, roomId)) : Promise.resolve()}
              onRestore={() => selectedSource && floorId ? act(() => restoreRoom(projectId, floorId, selectedSource.id)) : Promise.resolve()}
              onRestoreRevision={(revisionId) => selectedSource && floorId ? act(() => restoreRoomRevision(projectId, floorId, selectedSource.id, revisionId)) : Promise.resolve()}
              onDeleteCutout={(cutoutId) => selectedSource && floorId ? act(() => deleteRoomCutout(projectId, floorId, selectedSource.id, cutoutId)) : Promise.resolve()}
              onResetToModel={() => selectedSource && floorId ? act(() => resetRoomToModel(projectId, floorId, selectedSource.id)) : Promise.resolve()}
              onResetToCorrected={() => selectedSource && floorId ? act(() => resetRoomToCorrected(projectId, floorId, selectedSource.id)) : Promise.resolve()}
            />
          )}
          {error || analysis.error ? <div className="px-5 pb-5"><ErrorMessage message={error || analysis.error || ""} /></div> : null}
        </aside>
      </div>

      {autoFixPreview ? (
        <RoomAutoFixPreviewDialog
          preview={autoFixPreview}
          onClose={() => setAutoFixPreview(null)}
          onApply={applyAutoFixPreview}
        />
      ) : null}

      <div className="flex items-center justify-between border-t border-slate-200 bg-white px-6 py-4">
        <Link className="inline-flex h-11 items-center rounded-xl border border-slate-200 px-5 text-sm font-semibold text-slate-700" href={appRoutes.workflowStep(projectId, "walls")}>Back to Walls</Link>
        <Link className="inline-flex h-11 items-center rounded-xl bg-blue-600 px-5 text-sm font-semibold text-white" href={appRoutes.workflowStep(projectId, "review")}>Continue to Review</Link>
      </div>
    </WorkflowStepPage>
  );
}
