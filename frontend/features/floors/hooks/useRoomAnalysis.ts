"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  analyzeRooms,
  confirmAllRooms,
  interpretFloorRooms,
  precisionRefineRooms,
  recalculateRooms,
} from "../api";

export function useRoomAnalysis(projectId: string, floorId: string | null) {
  const client = useQueryClient();
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: "analyze" | "recalculate" | "confirm" | "interpret" | "precision") {
    if (!floorId) return;
    setRunning(true);
    setError(null);
    try {
      if (action === "analyze") await analyzeRooms(projectId, floorId);
      if (action === "recalculate") await recalculateRooms(projectId, floorId);
      if (action === "confirm") await confirmAllRooms(projectId, floorId);
      if (action === "interpret") await interpretFloorRooms(projectId, floorId);
      if (action === "precision") await precisionRefineRooms(projectId, floorId);
      await client.invalidateQueries({ queryKey: ["floors", projectId] });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The room action could not be completed.");
    } finally {
      setRunning(false);
    }
  }

  return {
    running,
    error,
    analyze: () => run("analyze"),
    recalculate: () => run("recalculate"),
    confirmAll: () => run("confirm"),
    interpret: () => run("interpret"),
    precisionRefine: () => run("precision"),
  };
}
