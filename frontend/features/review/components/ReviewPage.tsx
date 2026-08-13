"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { WorkflowStepPage } from "@/features/workflow/components/WorkflowStepPage";
import { Button } from "@/shared/components/Button";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import { appRoutes } from "@/shared/constants/appRoutes";
import { confirmReview, getReviewState, updateReviewField } from "../api";
import type { ReviewItem } from "../types";
import { ReviewViewTabs } from "./ReviewViewTabs";

const categories = ["all", "door", "window", "wall", "floor", "needs_review"] as const;
type Category = typeof categories[number];
const queryKey = (projectId: string, floorId: string | null, category: string) => ["review", projectId, floorId, category] as const;

function display(value: unknown, digits = 0): string {
  if (value == null || value === "") return "—";
  if (typeof value === "number") return digits ? value.toFixed(digits) : String(value);
  return String(value);
}

function itemCode(item: ReviewItem): string {
  return String(item.data.type_code || item.data.wall_type || item.data.floor_type_code || "—");
}

function itemMeasure(item: ReviewItem): string {
  if (item.entity_type === "door" || item.entity_type === "window") {
    const width = item.data.width_mm;
    const height = item.data.height_mm;
    return width && height ? `${display(width)} × ${display(height)} mm` : "Size needs review";
  }
  if (item.entity_type === "wall") return item.data.net_area_m2 ? `${display(item.data.net_area_m2, 2)} m² net` : "Area needs review";
  return item.data.area_m2 ? `${display(item.data.area_m2, 2)} m²` : "Area needs review";
}

function itemFinish(item: ReviewItem): string {
  if (item.entity_type === "door" || item.entity_type === "window") {
    return String(item.data.material || item.data.frame_material || item.data.finish || "—");
  }
  if (item.entity_type === "wall") {
    return String(item.data.side_1_finish || item.data.side_2_finish || item.data.classification || "—");
  }
  return String(item.data.floor_finish || item.data.room_name || "—");
}


function itemSource(item: ReviewItem): string {
  const sources = item.data.value_sources as Record<string, string> | undefined;
  if (!sources) return String(item.data.source || "Saved");
  const priority = ["user_confirmed", "schedule", "specification", "drawing_note", "calculated", "model", "default"];
  const values = new Set(Object.values(sources));
  const selected = priority.find((value) => values.has(value)) || "saved";
  return ({
    user_confirmed: "User confirmed", schedule: "Schedule", specification: "Specification",
    drawing_note: "Drawing detail", calculated: "Measured from plan", model: "Model", default: "Estimated", saved: "Saved",
  } as Record<string, string>)[selected] || "Saved";
}

function statusClass(status: ReviewItem["status"]): string {
  if (status === "confirmed") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (status === "needs_review") return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-blue-200 bg-blue-50 text-blue-700";
}

export function ReviewPage({ projectId }: { projectId: string }) {
  const client = useQueryClient();
  const [floorId, setFloorId] = useState<string | null>(null);
  const [category, setCategory] = useState<Category>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: queryKey(projectId, floorId, category),
    queryFn: () => getReviewState(projectId, floorId, category),
    refetchOnWindowFocus: false,
    refetchOnMount: "always",
    staleTime: 0,
    placeholderData: (previous) => previous,
    refetchInterval: (result) => result.state.data?.active_jobs?.length ? 2500 : false,
  });
  const state = query.data;
  const selected = state?.items.find((item) => item.id === selectedId) || null;

  useEffect(() => {
    setChecked(new Set());
    setSelectedId(null);
  }, [category, floorId]);

  function refresh() {
    void client.invalidateQueries({ queryKey: ["review", projectId], refetchType: "active" });
    void client.invalidateQueries({ queryKey: ["workflow", projectId, "summary"], refetchType: "active" });
    void client.invalidateQueries({ queryKey: ["boq", projectId], refetchType: "active" });
  }

  async function act(action: () => Promise<unknown>) {
    setSaving(true);
    setError(null);
    try {
      await action();
      refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The review could not be updated.");
    } finally {
      setSaving(false);
    }
  }

  const totals = useMemo(() => ({
    all: state?.counts.all || 0,
    ready: state?.counts.ready || 0,
    confirmed: state?.counts.confirmed || 0,
    needsReview: state?.counts.needs_review || 0,
  }), [state]);

  function sourceLink(item: ReviewItem): string {
    if (item.entity_type === "wall") return appRoutes.workflowStep(projectId, "walls");
    if (item.entity_type === "floor") return appRoutes.workflowStep(projectId, "floors");
    return appRoutes.workflowStep(projectId, "model-review");
  }

  return (
    <WorkflowStepPage projectId={projectId} stepKey="review">
      <div className="flex justify-end border-b border-slate-200 bg-white px-5 py-3">
        <ReviewViewTabs projectId={projectId} active="items" />
      </div>

      <div className="border-b border-slate-200 bg-white px-5 py-4">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Summary label="Project items" value={totals.all} />
          <Summary label="Ready" value={totals.ready} tone="blue" />
          <Summary label="Needs review" value={totals.needsReview} tone="amber" />
          <Summary label="Confirmed" value={totals.confirmed} tone="green" />
        </div>
      </div>

      <div className="grid min-h-[690px] grid-cols-[210px_minmax(0,1fr)_340px] overflow-hidden">
        <aside className="border-r border-slate-200 bg-white p-4">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Floors</p>
          <button
            type="button"
            onClick={() => setFloorId(null)}
            className={!floorId ? "w-full rounded-xl border border-blue-200 bg-blue-50 p-3 text-left" : "w-full rounded-xl border border-slate-200 p-3 text-left hover:border-blue-200"}
          >
            <div className="flex justify-between gap-2"><span className="text-sm font-semibold">All Floors</span><span className="text-xs text-slate-500">{totals.all}</span></div>
            <p className="mt-2 text-xs text-slate-500">{totals.needsReview} need review</p>
          </button>
          <div className="mt-2 space-y-2">
            {state?.floors.map((floor) => (
              <button
                key={floor.id}
                type="button"
                onClick={() => setFloorId(floor.id)}
                className={floorId === floor.id ? "w-full rounded-xl border border-blue-200 bg-blue-50 p-3 text-left" : "w-full rounded-xl border border-slate-200 p-3 text-left hover:border-blue-200"}
              >
                <div className="flex justify-between gap-2"><span className="text-sm font-semibold">{floor.name}</span><span className="text-xs text-slate-500">{floor.total}</span></div>
                <p className="mt-2 text-xs text-slate-500">{floor.ready || 0} ready · {floor.needs_review} review</p>
              </button>
            ))}
          </div>
        </aside>

        <main className="min-w-0 border-r border-slate-200 bg-white">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
            <div className="flex flex-wrap gap-1.5">
              {categories.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setCategory(item)}
                  className={category === item ? "rounded-lg bg-slate-950 px-3 py-2 text-sm font-semibold capitalize text-white" : "rounded-lg px-3 py-2 text-sm font-semibold capitalize text-slate-600 hover:bg-slate-50"}
                >
                  {item.replace("_", " ")} <span className="ml-1 text-xs opacity-70">{state?.counts[item] || 0}</span>
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={!checked.size || saving} onClick={() => void act(() => confirmReview(projectId, [...checked], "selected", floorId))}>Confirm selected</Button>
              <Button disabled={saving} onClick={() => void act(() => confirmReview(projectId, [], floorId ? "floor" : "project", floorId))}>Confirm all</Button>
            </div>
          </div>

          <div className="max-h-[640px] overflow-auto">
            <table className="w-full border-collapse text-left text-sm">
              <thead className="sticky top-0 z-10 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="w-12 px-4 py-3"></th>
                  <th className="px-4 py-3">Item</th>
                  <th className="px-4 py-3">Element</th>
                  <th className="px-4 py-3">Size / quantity</th>
                  <th className="px-4 py-3">Material / finish</th>
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {state?.items.map((item) => (
                  <tr
                    key={item.id}
                    onClick={() => setSelectedId(item.id)}
                    className={item.id === selectedId ? "cursor-pointer border-t border-slate-200 bg-blue-50" : "cursor-pointer border-t border-slate-200 hover:bg-slate-50"}
                  >
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={checked.has(item.id)}
                        disabled={item.critical}
                        onClick={(event) => event.stopPropagation()}
                        onChange={(event) => setChecked((current) => {
                          const next = new Set(current);
                          event.target.checked ? next.add(item.id) : next.delete(item.id);
                          return next;
                        })}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-semibold text-slate-900">{item.display_number || item.title}</p>
                      <p className="mt-1 text-xs text-slate-500">{String(item.data.floor || "")}</p>
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-medium capitalize text-slate-800">{item.entity_type}</p>
                      <p className="mt-1 text-xs text-slate-500">{itemCode(item)}</p>
                    </td>
                    <td className="px-4 py-3 font-medium text-slate-800">{itemMeasure(item)}</td>
                    <td className="px-4 py-3 text-slate-600">{itemFinish(item)}</td>
                    <td className="px-4 py-3 text-xs font-medium text-slate-500">{itemSource(item)}</td>
                    <td className="px-4 py-3"><span className={`rounded-full border px-2.5 py-1 text-xs font-semibold capitalize ${statusClass(item.status)}`}>{item.status.replace("_", " ")}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {state && !state.items.length ? <div className="p-12 text-center text-sm text-slate-500">No items match this view.</div> : null}
          </div>
        </main>

        <aside className="overflow-y-auto bg-white p-5">
          {selected ? (
            <ReviewDetails
              item={selected}
              saving={saving}
              onEdit={(field, value) => act(() => updateReviewField(projectId, selected.id, field, value))}
              sourceHref={sourceLink(selected)}
            />
          ) : <p className="text-sm text-slate-500">Select an item to review its current saved details.</p>}
          {error ? <div className="mt-4"><ErrorMessage message={error} /></div> : null}
        </aside>
      </div>

      <div className="flex items-center justify-between border-t border-slate-200 bg-white px-6 py-4">
        <Link className="inline-flex h-11 items-center rounded-xl border border-slate-200 px-5 text-sm font-semibold text-slate-700" href={appRoutes.workflowStep(projectId, "floors")}>Back to Floors</Link>
        <Link className="inline-flex h-11 items-center rounded-xl bg-blue-600 px-5 text-sm font-semibold text-white" href={appRoutes.workflowStep(projectId, "boq")}>Continue to BOQ</Link>
      </div>
    </WorkflowStepPage>
  );
}

function Summary({ label, value, tone = "slate" }: { label: string; value: number; tone?: "slate" | "blue" | "amber" | "green" }) {
  const tones = {
    slate: "bg-slate-50 text-slate-900",
    blue: "bg-blue-50 text-blue-800",
    amber: "bg-amber-50 text-amber-800",
    green: "bg-emerald-50 text-emerald-800",
  };
  return <div className={`rounded-xl border border-slate-200 px-4 py-3 ${tones[tone]}`}><p className="text-xs font-semibold uppercase tracking-wide opacity-65">{label}</p><p className="mt-1 text-2xl font-semibold">{value}</p></div>;
}

function ReviewDetails({ item, saving, onEdit, sourceHref }: { item: ReviewItem; saving: boolean; onEdit: (field: string, value: unknown) => Promise<void>; sourceHref: string }) {
  const editable = item.entity_type === "wall"
    ? ["classification", "wall_type", "thickness_mm", "side_1_finish", "side_2_finish"]
    : item.entity_type === "floor"
      ? ["room_name", "floor_type_code", "floor_finish"]
      : ["type_code", "width_mm", "height_mm", "material", "frame_material", "finish", ...(item.entity_type === "window" ? ["glass_type"] : [])];
  const warnings = Array.isArray(item.data.warnings) ? item.data.warnings.map(String) : [];
  const missing = Array.isArray(item.data.missing_fields) ? item.data.missing_fields.map(String) : [];
  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[.14em] text-slate-400">Selected item</p>
        <h3 className="mt-1 text-xl font-semibold">{item.display_number || item.title}</h3>
        <p className="mt-1 text-sm capitalize text-slate-500">{item.entity_type} · {itemCode(item)}</p>
      </div>
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
        <div className="flex justify-between gap-3"><span className="text-slate-500">Floor</span><strong>{String(item.data.floor || "—")}</strong></div>
        <div className="mt-2 flex justify-between gap-3"><span className="text-slate-500">Measure</span><strong className="text-right">{itemMeasure(item)}</strong></div>
        <div className="mt-2 flex justify-between gap-3"><span className="text-slate-500">Material / finish</span><strong className="text-right">{itemFinish(item)}</strong></div>
        <div className="mt-2 flex justify-between gap-3"><span className="text-slate-500">Resolved from</span><strong className="text-right">{itemSource(item)}</strong></div>
        {item.data.drawing_tag ? <div className="mt-2 flex justify-between gap-3"><span className="text-slate-500">Drawing tag</span><strong>{String(item.data.drawing_tag)}</strong></div> : null}
      </div>
      {missing.length || warnings.length ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
          {missing.length ? <p><strong>Missing:</strong> {missing.map((value) => value.replaceAll("_", " ")).join(", ")}</p> : null}
          {warnings.map((warning) => <p key={warning} className="mt-1">{warning}</p>)}
        </div>
      ) : null}
      <div className="space-y-3">
        {editable.map((field) => {
          const backendField = field === "room_name" ? "name" : field;
          return (
            <label key={field} className="block text-sm font-medium capitalize">
              {field.replaceAll("_", " ")}
              <input
                className="input mt-1 w-full"
                defaultValue={item.data[field] == null ? "" : String(item.data[field])}
                onBlur={(event) => {
                  const raw = event.target.value;
                  const next = field.endsWith("_mm") ? Number(raw) : raw;
                  if (raw !== String(item.data[field] ?? "")) void onEdit(backendField, next);
                }}
                disabled={saving}
              />
            </label>
          );
        })}
      </div>
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-600">Source version {item.source_version}. Review version {item.review_version}.</div>
      <Link href={sourceHref} className="inline-flex h-10 w-full items-center justify-center rounded-md border border-slate-200 text-sm font-semibold text-slate-700 hover:bg-slate-50">Open source page</Link>
    </div>
  );
}
