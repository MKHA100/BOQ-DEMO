"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Point } from "@/features/drawing/types";
import { deletePoint, insertPoint, makeRectangle, moveEdge, simplifyPoints } from "../geometry/editorGeometry";
import { straightenPolygon } from "../geometry/snapping";

function clonePoints(points: Point[]): Point[] {
  return points.map((point) => ({ x: point.x, y: point.y }));
}

function geometryFingerprint(points: Point[]): string {
  return points.map((point) => `${point.x.toFixed(4)},${point.y.toFixed(4)}`).join("|");
}

export function useRoomEditor(roomId: string | null, source: Point[], geometryVersion = 0) {
  const sourceRef = useRef<Point[]>(source);
  sourceRef.current = source;
  const sourceFingerprint = useMemo(() => geometryFingerprint(source), [source]);

  const [history, setHistory] = useState<Point[][]>(() => [clonePoints(source)]);
  const [index, setIndex] = useState(0);
  const [selectedVertex, setSelectedVertex] = useState<number | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<number | null>(null);

  useEffect(() => {
    const next = clonePoints(sourceRef.current);
    setHistory((current) => {
      const active = current[0] || [];
      if (geometryFingerprint(active) === sourceFingerprint && current.length === 1) return current;
      return [next];
    });
    setIndex((current) => current === 0 ? current : 0);
    setSelectedVertex((current) => current === null ? current : null);
    setSelectedEdge((current) => current === null ? current : null);
  }, [geometryVersion, roomId, sourceFingerprint]);

  const points = history[index] || [];
  const apply = useCallback((next: Point[]) => {
    setHistory((current) => {
      const base = current.slice(0, index + 1);
      return [...base, clonePoints(next)];
    });
    setIndex((current) => current + 1);
  }, [index]);

  const updateVertex = useCallback(
    (vertexIndex: number, point: Point) => apply(
      points.map((item, itemIndex) => itemIndex === vertexIndex ? point : item),
    ),
    [apply, points],
  );

  const reset = useCallback(() => {
    setHistory([clonePoints(sourceRef.current)]);
    setIndex(0);
    setSelectedVertex(null);
    setSelectedEdge(null);
  }, []);

  return {
    points,
    dirty: index > 0,
    selectedVertex,
    selectedEdge,
    canUndo: index > 0,
    canRedo: index < history.length - 1,
    selectVertex: setSelectedVertex,
    selectEdge: setSelectedEdge,
    updateVertex,
    addVertex: (edgeIndex: number, point: Point) => apply(insertPoint(points, edgeIndex, point)),
    removeVertex: (vertexIndex: number) => apply(deletePoint(points, vertexIndex)),
    shiftEdge: (edgeIndex: number, delta: Point) => apply(moveEdge(points, edgeIndex, delta)),
    simplify: () => apply(simplifyPoints(points)),
    rectangle: () => apply(makeRectangle(points)),
    straighten: () => apply(straightenPolygon(points)),
    replace: apply,
    undo: () => setIndex((current) => Math.max(0, current - 1)),
    redo: () => setIndex((current) => Math.min(history.length - 1, current + 1)),
    reset,
  };
}
