"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { Point } from "@/features/drawing/types";
import { distance } from "@/features/drawing/geometry";
import { WorkflowStepPage } from "@/features/workflow/components/WorkflowStepPage";
import { Button } from "@/shared/components/Button";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import { appRoutes } from "@/shared/constants/appRoutes";
import { getScaleState, saveFloorCalibration } from "../api";
import type { ScaleFloor } from "../types";
import { millimetresToFeetAndInches, toMillimetres, type ScaleUnit } from "../utils/units";
import { CalibrationCanvas } from "./CalibrationCanvas";
import { ScaleStatusPill } from "./ScaleStatusPill";

const queryKey = (projectId: string) => ["scale", projectId] as const;

export function ScalePage({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const stateQuery = useQuery({
    queryKey: queryKey(projectId), queryFn: () => getScaleState(projectId),
    refetchOnWindowFocus: false, refetchOnMount: false, staleTime: 60 * 60_000,
    placeholderData: (previous) => previous,
  });
  const state = stateQuery.data;
  const [selectedFloorId, setSelectedFloorId] = useState<string | null>(null);
  const [pointA, setPointA] = useState<Point | null>(null);
  const [pointB, setPointB] = useState<Point | null>(null);
  const [verificationA, setVerificationA] = useState<Point | null>(null);
  const [verificationB, setVerificationB] = useState<Point | null>(null);
  const [distanceValue, setDistanceValue] = useState("1");
  const [distanceFeet, setDistanceFeet] = useState("");
  const [distanceInches, setDistanceInches] = useState("");
  const [unit, setUnit] = useState<ScaleUnit>("m");
  const [verificationValue, setVerificationValue] = useState("");
  const [verificationFeet, setVerificationFeet] = useState("");
  const [verificationInches, setVerificationInches] = useState("");
  const [verificationUnit, setVerificationUnit] = useState<ScaleUnit>("m");
  const [mode, setMode] = useState<"calibration" | "verification" | "pan">("calibration");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!state?.floors.length) return;
    const saved = typeof window !== "undefined" ? window.sessionStorage.getItem(`autoboq:scale:floor:${projectId}`) : null;
    const next = state.floors.find((floor) => floor.id === saved) ?? state.floors.find((floor) => floor.status === "not_calibrated") ?? state.floors[0];
    setSelectedFloorId((current) => current && state.floors.some((floor) => floor.id === current) ? current : next.id);
  }, [projectId, state?.floors]);

  const floor = useMemo(() => state?.floors.find((item) => item.id === selectedFloorId) ?? null, [selectedFloorId, state?.floors]);

  useEffect(() => {
    if (!floor) return;
    window.sessionStorage.setItem(`autoboq:scale:floor:${projectId}`, floor.id);
    const calibration = floor.calibration;
    setPointA(calibration?.point_a ?? null);
    setPointB(calibration?.point_b ?? null);
    setVerificationA(calibration?.verification_points?.point_a ?? null);
    setVerificationB(calibration?.verification_points?.point_b ?? null);
    const useImperial = calibration?.input_unit === "ft_in";
    const mainImperial = millimetresToFeetAndInches(calibration?.real_distance_mm ?? 0);
    const verificationImperial = millimetresToFeetAndInches(calibration?.verification_expected_mm ?? 0);
    setDistanceValue(calibration ? String(calibration.real_distance_mm / 1000) : "1");
    setDistanceFeet(useImperial && calibration ? String(mainImperial.feet) : "");
    setDistanceInches(useImperial && calibration ? String(mainImperial.inches) : "");
    setUnit(useImperial ? "ft_in" : "m");
    setVerificationValue(!useImperial && calibration?.verification_expected_mm ? String(calibration.verification_expected_mm / 1000) : "");
    setVerificationFeet(useImperial && calibration?.verification_expected_mm ? String(verificationImperial.feet) : "");
    setVerificationInches(useImperial && calibration?.verification_expected_mm ? String(verificationImperial.inches) : "");
    setVerificationUnit(useImperial ? "ft_in" : "m");
    setMode("calibration");
  }, [floor?.id, projectId]);

  function pick(point: Point) {
    setError(null);
    if (mode === "calibration") {
      if (!pointA || pointB) {
        setPointA(point);
        setPointB(null);
      } else {
        setPointB(point);
      }
      return;
    }
    if (mode === "verification") {
      if (!verificationA || verificationB) {
        setVerificationA(point);
        setVerificationB(null);
      } else {
        setVerificationB(point);
      }
    }
  }

  async function save() {
    if (!floor || !pointA || !pointB) {
      setError("Select Point A and Point B.");
      return;
    }
    const value = Number(distanceValue);
    const feet = Number(distanceFeet || 0);
    const inches = Number(distanceInches || 0);
    const imperialIsValid = unit !== "ft_in" || (
      Number.isInteger(feet) && feet >= 0 && Number.isFinite(inches) && inches >= 0 && inches < 12
    );
    const realDistanceMm = toMillimetres(value, unit, feet, inches);
    if (!imperialIsValid || !Number.isFinite(realDistanceMm) || realDistanceMm <= 0 || distance(pointA, pointB) < 5) {
      setError("Enter a valid distance and select two points further apart.");
      return;
    }
    const verificationDistance = Number(verificationValue);
    const verificationFeetValue = Number(verificationFeet || 0);
    const verificationInchesValue = Number(verificationInches || 0);
    const hasVerificationValue = verificationUnit === "ft_in"
      ? Boolean(verificationFeet || verificationInches)
      : Boolean(verificationValue);
    const verificationDistanceMm = toMillimetres(
      verificationDistance,
      verificationUnit,
      verificationFeetValue,
      verificationInchesValue,
    );
    const verificationImperialIsValid = verificationUnit !== "ft_in" || (
      Number.isInteger(verificationFeetValue) && verificationFeetValue >= 0
      && Number.isFinite(verificationInchesValue) && verificationInchesValue >= 0
      && verificationInchesValue < 12
    );
    if ((verificationA || verificationB || hasVerificationValue) && (
      !verificationA || !verificationB || !verificationImperialIsValid
      || !Number.isFinite(verificationDistanceMm) || verificationDistanceMm <= 0
    )) {
      setError("Complete the optional verification or clear it.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await saveFloorCalibration(projectId, floor.id, {
        point_a: pointA,
        point_b: pointB,
        unit,
        ...(unit === "ft_in"
          ? { feet, inches }
          : { real_distance: value }),
        crop_version: floor.crop_version,
        ...(verificationA && verificationB && verificationDistanceMm > 0 ? {
          verification: {
            point_a: verificationA,
            point_b: verificationB,
            unit: verificationUnit,
            ...(verificationUnit === "ft_in"
              ? { feet: verificationFeetValue, inches: verificationInchesValue }
              : { expected_distance: verificationDistance }),
          },
        } : {}),
      });
      void queryClient.invalidateQueries({ queryKey: queryKey(projectId), refetchType: "active" });
      void queryClient.invalidateQueries({ queryKey: ["workflow", projectId, "summary"], refetchType: "active" });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Calibration could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <WorkflowStepPage projectId={projectId} stepKey="scale">
      <div className="grid h-[calc(100dvh-286px)] min-h-[720px] max-h-[1100px] grid-cols-[170px_minmax(0,1fr)_285px] overflow-hidden">
        <aside className="min-h-0 overflow-y-auto border-r border-slate-200 bg-white p-4">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Floors</p>
          <div className="space-y-2">
            {state?.floors.map((item) => (
              <button
                type="button"
                key={item.id}
                onClick={() => setSelectedFloorId(item.id)}
                className={item.id === selectedFloorId ? "w-full rounded-xl border border-blue-200 bg-blue-50 p-3 text-left" : "w-full rounded-xl border border-slate-200 bg-white p-3 text-left hover:border-blue-200"}
              >
                <div className="flex flex-col items-start gap-2">
                  <span className="text-sm font-semibold leading-5 text-slate-900">{item.name}</span>
                  <ScaleStatusPill status={item.status} />
                </div>
                <p className="mt-2 text-xs text-slate-500">{item.calibration ? `${item.calibration.mm_per_pixel.toFixed(4)} mm/px` : "Known-distance calibration"}</p>
              </button>
            ))}
          </div>
        </aside>

        <main className="min-h-0 min-w-0 overflow-hidden border-r border-slate-200">
          {floor ? (
            <CalibrationCanvas
              imagePath={floor.drawing_url}
              width={floor.original_page_width || 1}
              height={floor.original_page_height || 1}
              mode={mode}
              pointA={pointA}
              pointB={pointB}
              verificationA={verificationA}
              verificationB={verificationB}
              onPoint={pick}
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-slate-500">Loading floor drawings</div>
          )}
        </main>

        <aside className="min-h-0 overflow-y-auto bg-white p-4">
          <h3 className="text-lg font-semibold text-slate-950">Calibrate drawing</h3>
          <p className="mt-1 text-sm leading-6 text-slate-500">Select two points on a known dimension, then enter its real distance.</p>
          <div className="mt-5 grid grid-cols-2 gap-2">
            <Button variant={mode === "calibration" ? "primary" : "secondary"} onClick={() => setMode("calibration")}>Select points</Button>
            <Button variant={mode === "pan" ? "primary" : "secondary"} onClick={() => setMode("pan")}>Hand</Button>
          </div>
          <div className="mt-5 rounded-xl border border-slate-200 p-4">
            <div className="flex items-center justify-between text-sm"><span>Point A</span><strong>{pointA ? `${pointA.x.toFixed(1)}, ${pointA.y.toFixed(1)}` : "Not selected"}</strong></div>
            <div className="mt-3 flex items-center justify-between text-sm"><span>Point B</span><strong>{pointB ? `${pointB.x.toFixed(1)}, ${pointB.y.toFixed(1)}` : "Not selected"}</strong></div>
            <div className="mt-3 flex items-center justify-between text-sm"><span>Pixel distance</span><strong>{pointA && pointB ? distance(pointA, pointB).toFixed(2) : "—"}</strong></div>
          </div>
          {floor?.dimension_suggestions?.length ? (
            <div className="mt-5 rounded-xl border border-blue-100 bg-blue-50 p-3">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-blue-600">Drawing suggestions</p>
              <p className="mt-1 text-xs text-blue-700">Choose a printed dimension, then verify it with another one.</p>
              <div className="mt-3 space-y-2">
                {floor?.dimension_suggestions.slice(0, 5).map((suggestion) => (
                  <button key={suggestion.id} type="button" className="flex w-full items-center justify-between rounded-lg border border-blue-100 bg-white px-3 py-2 text-left text-sm hover:border-blue-300" onClick={() => {
                    const imperial = millimetresToFeetAndInches(suggestion.value_mm);
                    setPointA(suggestion.point_a); setPointB(suggestion.point_b);
                    setDistanceValue(""); setDistanceFeet(String(imperial.feet)); setDistanceInches(String(imperial.inches)); setUnit("ft_in"); setMode("calibration");
                  }}>
                    <span className="font-semibold text-slate-900">Scale {suggestion.display_scale || suggestion.label_text}</span>
                    <span className="text-xs text-slate-500">Use</span>
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <div className="mt-5">
            <label><span className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Unit</span><select className="input mt-2" value={unit} onChange={(event) => setUnit(event.target.value as ScaleUnit)}><option value="mm">mm</option><option value="cm">cm</option><option value="m">m</option><option value="ft_in">ft + in</option></select></label>
            {unit === "ft_in" ? (
              <div className="mt-3 grid grid-cols-2 gap-2">
                <label><span className="text-xs font-semibold text-slate-500">Feet (′)</span><input className="input mt-1" type="number" min="0" step="1" placeholder="14" value={distanceFeet} onChange={(event) => setDistanceFeet(event.target.value)} /></label>
                <label><span className="text-xs font-semibold text-slate-500">Inches (″)</span><input className="input mt-1" type="number" min="0" max="11.999" step="0.125" placeholder="5" value={distanceInches} onChange={(event) => setDistanceInches(event.target.value)} /></label>
                <p className="col-span-2 text-xs text-slate-500">For 14′-5″, enter 14 feet and 5 inches.</p>
              </div>
            ) : (
              <label className="mt-3 block"><span className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Real distance</span><input className="input mt-2" type="number" min="0.001" value={distanceValue} onChange={(event) => setDistanceValue(event.target.value)} /></label>
            )}
          </div>
          {pointA && pointB && toMillimetres(Number(distanceValue), unit, Number(distanceFeet || 0), Number(distanceInches || 0)) > 0 ? <p className="mt-3 rounded-xl bg-blue-50 p-3 text-sm font-semibold text-blue-700">{(toMillimetres(Number(distanceValue), unit, Number(distanceFeet || 0), Number(distanceInches || 0)) / distance(pointA, pointB)).toFixed(4)} mm per pixel</p> : null}

          <div className="mt-6 border-t border-slate-200 pt-5">
            <div className="flex items-center justify-between"><div><h4 className="text-sm font-semibold text-slate-900">Verification</h4><p className="mt-1 text-xs text-slate-500">Optional second known dimension</p></div><Button variant={mode === "verification" ? "primary" : "secondary"} onClick={() => setMode("verification")}>Select</Button></div>
            <select className="input mt-3" value={verificationUnit} onChange={(event) => setVerificationUnit(event.target.value as ScaleUnit)}><option value="mm">mm</option><option value="cm">cm</option><option value="m">m</option><option value="ft_in">ft + in</option></select>
            {verificationUnit === "ft_in" ? (
              <div className="mt-2 grid grid-cols-2 gap-2">
                <input className="input" type="number" min="0" step="1" placeholder="Feet" aria-label="Verification feet" value={verificationFeet} onChange={(event) => setVerificationFeet(event.target.value)} />
                <input className="input" type="number" min="0" max="11.999" step="0.125" placeholder="Inches" aria-label="Verification inches" value={verificationInches} onChange={(event) => setVerificationInches(event.target.value)} />
              </div>
            ) : <input className="input mt-2" type="number" min="0.001" placeholder="Expected distance" value={verificationValue} onChange={(event) => setVerificationValue(event.target.value)} />}
          </div>

          {floor?.calibration?.verification_difference_percent != null ? <div className={`mt-4 rounded-xl p-3 text-sm font-semibold ${floor.calibration.verification_difference_percent <= 2 ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>{floor.calibration.verification_difference_percent <= 2 ? "Accurate" : "Check Calibration"} — {floor.calibration.verification_difference_percent.toFixed(2)}%</div> : null}
          {error ? <div className="mt-4"><ErrorMessage message={error} /></div> : null}
          <Button className="mt-5 h-11 w-full" onClick={() => void save()} disabled={saving || !floor?.drawing_url}>{saving ? "Saving" : "Save calibration"}</Button>
        </aside>
      </div>
      <div className="flex items-center justify-between border-t border-slate-200 bg-white px-6 py-4">
        <Link className="inline-flex h-11 items-center rounded-xl border border-slate-200 px-5 text-sm font-semibold text-slate-700 hover:bg-slate-50" href={appRoutes.workflowStep(projectId, "specifications")}>Back to Schedules & Specifications</Link>
        <Link className="inline-flex h-11 items-center rounded-xl bg-blue-600 px-5 text-sm font-semibold text-white hover:bg-blue-700" href={appRoutes.workflowStep(projectId, "model-review")}>Continue to Model Review</Link>
      </div>
    </WorkflowStepPage>
  );
}
