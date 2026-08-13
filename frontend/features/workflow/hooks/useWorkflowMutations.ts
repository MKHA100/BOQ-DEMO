"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createFloor, saveCalibration, updateElementProperty, updateRoomGeometry } from "../api";
import { workflowQueryKeys } from "../queryKeys";
import type { CalibrationRecord, ElementPropertyRecord, ElementRecord, PagedResult, RoomRecord } from "../readTypes";
import type { FloorSummary, ProjectWorkflowSummary, ValueSource } from "../types";

function floorName(levelIndex: number): string {
  if (levelIndex === 0) return "Ground Floor";
  const ordinal: Record<number, string> = { 1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth" };
  return ordinal[levelIndex] ? `${ordinal[levelIndex]} Floor` : `Floor ${levelIndex}`;
}

export function useCreateFloor(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name?: string; level_index?: number }) => createFloor(projectId, payload),
    onMutate: async (payload) => {
      await queryClient.cancelQueries({ queryKey: workflowQueryKeys.summary(projectId) });
      const previous = queryClient.getQueryData<ProjectWorkflowSummary>(workflowQueryKeys.summary(projectId));
      if (previous) {
        const levelIndex = payload.level_index ?? previous.floors.length;
        const optimistic: FloorSummary = {
          id: `pending-floor-${Date.now()}`,
          project_id: projectId,
          name: payload.name || floorName(levelIndex),
          level_index: levelIndex,
          status: "not_ready",
          versions: {},
          counts: { elements: 0, walls: 0, rooms: 0, review_issues: 0 },
        };
        queryClient.setQueryData<ProjectWorkflowSummary>(workflowQueryKeys.summary(projectId), {
          ...previous,
          floors: [...previous.floors, optimistic],
          counts: { ...previous.counts, floors: (previous.counts.floors || 0) + 1 },
        });
      }
      return { previous };
    },
    onError: (_error, _payload, context) => {
      if (context?.previous) queryClient.setQueryData(workflowQueryKeys.summary(projectId), context.previous);
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: workflowQueryKeys.summary(projectId) });
      void queryClient.invalidateQueries({ queryKey: workflowQueryKeys.floors(projectId) });
    },
  });
}

export function useUpdateElementProperty(projectId: string, floorId: string) {
  const queryClient = useQueryClient();
  const key = workflowQueryKeys.elements(projectId, floorId);
  return useMutation({
    mutationFn: (input: {
      elementId: string;
      propertyName: string;
      value: unknown;
      unit?: string;
      source: ValueSource;
      confirm?: boolean;
    }) =>
      updateElementProperty(projectId, input.elementId, input.propertyName, {
        value: input.value,
        unit: input.unit,
        source: input.source,
        confirm: input.confirm,
      }),
    onMutate: async (input) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<PagedResult<ElementRecord>>(key);
      if (previous) {
        queryClient.setQueryData<PagedResult<ElementRecord>>(key, {
          ...previous,
          items: previous.items.map((element) => {
            if (element.id !== input.elementId) return element;
            const existing = element.properties.find((property) => property.property_name === input.propertyName);
            const optimistic: ElementPropertyRecord = {
              id: existing?.id || `pending-property-${Date.now()}`,
              project_id: projectId,
              floor_id: floorId,
              element_id: input.elementId,
              property_name: input.propertyName,
              value: input.value,
              unit: input.unit || null,
              source: input.confirm ? "user_confirmed" : input.source,
              source_priority: existing?.source_priority || 0,
              is_confirmed: Boolean(input.confirm),
              element_version: existing?.element_version || element.element_version,
            };
            return {
              ...element,
              properties: [...element.properties.filter((property) => property.property_name !== input.propertyName), optimistic],
            };
          }),
        });
      }
      return { previous };
    },
    onError: (_error, _input, context) => {
      if (context?.previous) queryClient.setQueryData(key, context.previous);
    },
    onSuccess: (result, input) => {
      const saved = result.record as ElementPropertyRecord;
      queryClient.setQueryData<PagedResult<ElementRecord>>(key, (current) =>
        current
          ? {
              ...current,
              items: current.items.map((element) =>
                element.id === input.elementId
                  ? {
                      ...element,
                      properties: [
                        ...element.properties.filter((property) => property.property_name !== input.propertyName),
                        saved,
                      ],
                    }
                  : element
              ),
            }
          : current
      );
      void queryClient.invalidateQueries({ queryKey: workflowQueryKeys.walls(projectId, floorId) });
      void queryClient.invalidateQueries({ queryKey: workflowQueryKeys.review(projectId, floorId) });
      void queryClient.invalidateQueries({ queryKey: workflowQueryKeys.boq(projectId, floorId) });
      void queryClient.invalidateQueries({ queryKey: workflowQueryKeys.summary(projectId) });
    },
  });
}

export function useSaveCalibration(projectId: string, floorId: string) {
  const queryClient = useQueryClient();
  const key = workflowQueryKeys.calibration(projectId, floorId);
  return useMutation({
    mutationFn: (payload: Parameters<typeof saveCalibration>[2]) => saveCalibration(projectId, floorId, payload),
    onMutate: async (payload) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<CalibrationRecord | null>(key);
      const pixelDistance = Math.hypot(payload.point_b.x - payload.point_a.x, payload.point_b.y - payload.point_a.y);
      queryClient.setQueryData<CalibrationRecord>(key, {
        id: previous?.id || `pending-calibration-${Date.now()}`,
        project_id: projectId,
        floor_id: floorId,
        point_a: payload.point_a,
        point_b: payload.point_b,
        pixel_distance: pixelDistance,
        real_distance: payload.real_distance,
        unit: payload.unit,
        units_per_pixel: payload.real_distance / pixelDistance,
        source_crop_version: payload.source_crop_version,
        scale_version: previous?.scale_version || 0,
        status: "confirmed",
      });
      return { previous };
    },
    onError: (_error, _payload, context) => queryClient.setQueryData(key, context?.previous ?? null),
    onSuccess: (result) => {
      queryClient.setQueryData(key, result.record as CalibrationRecord);
      for (const dependencyKey of [
        workflowQueryKeys.floor(projectId, floorId),
        workflowQueryKeys.elements(projectId, floorId),
        workflowQueryKeys.walls(projectId, floorId),
        workflowQueryKeys.rooms(projectId, floorId),
        workflowQueryKeys.review(projectId, floorId),
        workflowQueryKeys.boq(projectId, floorId),
        workflowQueryKeys.summary(projectId),
      ]) {
        void queryClient.invalidateQueries({ queryKey: dependencyKey });
      }
    },
  });
}

export function useUpdateRoomGeometry(projectId: string, floorId: string) {
  const queryClient = useQueryClient();
  const key = workflowQueryKeys.rooms(projectId, floorId);
  return useMutation({
    mutationFn: (input: { roomId: string; geometry: Record<string, unknown>; confirm?: boolean }) =>
      updateRoomGeometry(projectId, input.roomId, input.geometry, input.confirm),
    onMutate: async (input) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<PagedResult<RoomRecord>>(key);
      if (previous) {
        queryClient.setQueryData<PagedResult<RoomRecord>>(key, {
          ...previous,
          items: previous.items.map((room) =>
            room.id === input.roomId
              ? { ...room, geometry: input.geometry, user_confirmed: Boolean(input.confirm), status: "confirmed" }
              : room
          ),
        });
      }
      return { previous };
    },
    onError: (_error, _input, context) => {
      if (context?.previous) queryClient.setQueryData(key, context.previous);
    },
    onSuccess: (result, input) => {
      const saved = result.record as RoomRecord;
      queryClient.setQueryData<PagedResult<RoomRecord>>(key, (current) =>
        current
          ? { ...current, items: current.items.map((room) => (room.id === input.roomId ? saved : room)) }
          : current
      );
      void queryClient.invalidateQueries({ queryKey: workflowQueryKeys.review(projectId, floorId) });
      void queryClient.invalidateQueries({ queryKey: workflowQueryKeys.boq(projectId, floorId) });
      void queryClient.invalidateQueries({ queryKey: workflowQueryKeys.summary(projectId) });
    },
  });
}
