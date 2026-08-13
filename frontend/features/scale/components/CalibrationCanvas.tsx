"use client";

import type { Point } from "@/features/drawing/types";
import { DrawingCanvas } from "@/features/drawing/components/DrawingCanvas";
import { useAssetUrl } from "@/features/floor-plans/hooks/useAssetUrl";

export function CalibrationCanvas({
  imagePath,
  width,
  height,
  mode,
  pointA,
  pointB,
  verificationA,
  verificationB,
  onPoint,
}: {
  imagePath: string | null;
  width: number;
  height: number;
  mode: "calibration" | "verification" | "pan";
  pointA: Point | null;
  pointB: Point | null;
  verificationA: Point | null;
  verificationB: Point | null;
  onPoint: (point: Point) => void;
}) {
  const imageUrl = useAssetUrl(imagePath);
  return (
    <DrawingCanvas
      imageUrl={imageUrl}
      width={width}
      height={height}
      tool={mode === "pan" ? "pan" : "point"}
      onCanvasClick={onPoint}
    >
      {pointA ? <circle cx={pointA.x} cy={pointA.y} r={7} fill="#2563eb" stroke="white" strokeWidth={2} vectorEffect="non-scaling-stroke" /> : null}
      {pointB ? <circle cx={pointB.x} cy={pointB.y} r={7} fill="#2563eb" stroke="white" strokeWidth={2} vectorEffect="non-scaling-stroke" /> : null}
      {pointA && pointB ? <line x1={pointA.x} y1={pointA.y} x2={pointB.x} y2={pointB.y} stroke="#2563eb" strokeWidth={2} vectorEffect="non-scaling-stroke" /> : null}
      {verificationA ? <circle cx={verificationA.x} cy={verificationA.y} r={6} fill="#f59e0b" stroke="white" strokeWidth={2} vectorEffect="non-scaling-stroke" /> : null}
      {verificationB ? <circle cx={verificationB.x} cy={verificationB.y} r={6} fill="#f59e0b" stroke="white" strokeWidth={2} vectorEffect="non-scaling-stroke" /> : null}
      {verificationA && verificationB ? <line x1={verificationA.x} y1={verificationA.y} x2={verificationB.x} y2={verificationB.y} stroke="#f59e0b" strokeWidth={2} strokeDasharray="6 5" vectorEffect="non-scaling-stroke" /> : null}
    </DrawingCanvas>
  );
}
