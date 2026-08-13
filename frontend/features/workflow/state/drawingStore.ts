"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

type ViewState = {
  zoom: number;
  panX: number;
  panY: number;
  scrollTop: number;
  filter: string;
};

type DrawingState = {
  selectedFloorByProject: Record<string, string | null>;
  viewByScope: Record<string, ViewState>;
  unsavedPointsByScope: Record<string, Array<{ x: number; y: number }>>;
  setSelectedFloor: (projectId: string, floorId: string | null) => void;
  setView: (scope: string, patch: Partial<ViewState>) => void;
  setUnsavedPoints: (scope: string, points: Array<{ x: number; y: number }>) => void;
  clearUnsavedPoints: (scope: string) => void;
};

const defaultView: ViewState = { zoom: 1, panX: 0, panY: 0, scrollTop: 0, filter: "all" };

export const useDrawingStore = create<DrawingState>()(
  persist(
    (set) => ({
      selectedFloorByProject: {},
      viewByScope: {},
      unsavedPointsByScope: {},
      setSelectedFloor: (projectId, floorId) =>
        set((state) => ({ selectedFloorByProject: { ...state.selectedFloorByProject, [projectId]: floorId } })),
      setView: (scope, patch) =>
        set((state) => ({
          viewByScope: {
            ...state.viewByScope,
            [scope]: { ...(state.viewByScope[scope] || defaultView), ...patch },
          },
        })),
      setUnsavedPoints: (scope, points) =>
        set((state) => ({ unsavedPointsByScope: { ...state.unsavedPointsByScope, [scope]: points } })),
      clearUnsavedPoints: (scope) =>
        set((state) => {
          const next = { ...state.unsavedPointsByScope };
          delete next[scope];
          return { unsavedPointsByScope: next };
        }),
    }),
    {
      name: "autoboq-workflow-view",
      partialize: (state) => ({
        selectedFloorByProject: state.selectedFloorByProject,
        viewByScope: state.viewByScope,
      }),
    }
  )
);
