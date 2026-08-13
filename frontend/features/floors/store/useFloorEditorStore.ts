"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Point } from "@/features/drawing/types";

export type FloorEditorTool =
  | "select"
  | "pan"
  | "edit_vertex"
  | "add_vertex"
  | "delete_vertex"
  | "move_edge"
  | "draw_room"
  | "split"
  | "cutout"
  | "zone";

export type FloorEditorView = { zoom: number; pan: Point };

type FloorEditorState = {
  floorByProject: Record<string, string | null>;
  roomByProject: Record<string, string | null>;
  viewByFloor: Record<string, FloorEditorView>;
  tool: FloorEditorTool;
  setFloor: (projectId: string, floorId: string | null) => void;
  setRoom: (projectId: string, roomId: string | null) => void;
  setView: (floorId: string, view: FloorEditorView) => void;
  setTool: (tool: FloorEditorTool) => void;
};

const VIEW_EPSILON = 0.0001;

function sameView(current: FloorEditorView | undefined, next: FloorEditorView): boolean {
  if (!current) return false;
  return Math.abs(current.zoom - next.zoom) < VIEW_EPSILON
    && Math.abs(current.pan.x - next.pan.x) < VIEW_EPSILON
    && Math.abs(current.pan.y - next.pan.y) < VIEW_EPSILON;
}

function validView(view: FloorEditorView): boolean {
  return Number.isFinite(view.zoom)
    && view.zoom > 0
    && Number.isFinite(view.pan.x)
    && Number.isFinite(view.pan.y);
}

export const useFloorEditorStore = create<FloorEditorState>()(
  persist(
    (set) => ({
      floorByProject: {},
      roomByProject: {},
      viewByFloor: {},
      tool: "select",
      setFloor: (projectId, floorId) => set((state) => {
        if ((state.floorByProject[projectId] ?? null) === floorId) return state;
        return {
          floorByProject: {
            ...state.floorByProject,
            [projectId]: floorId,
          },
        };
      }),
      setRoom: (projectId, roomId) => set((state) => {
        if ((state.roomByProject[projectId] ?? null) === roomId) return state;
        return {
          roomByProject: {
            ...state.roomByProject,
            [projectId]: roomId,
          },
        };
      }),
      setView: (floorId, view) => set((state) => {
        if (!floorId || !validView(view) || sameView(state.viewByFloor[floorId], view)) return state;
        return {
          viewByFloor: {
            ...state.viewByFloor,
            [floorId]: {
              zoom: view.zoom,
              pan: { x: view.pan.x, y: view.pan.y },
            },
          },
        };
      }),
      setTool: (tool) => set((state) => (state.tool === tool ? state : { tool })),
    }),
    {
      name: "autoboq-floor-editor",
      partialize: (state) => ({
        floorByProject: state.floorByProject,
        roomByProject: state.roomByProject,
        viewByFloor: state.viewByFloor,
      }),
    },
  ),
);
