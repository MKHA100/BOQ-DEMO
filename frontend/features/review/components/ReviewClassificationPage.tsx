"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { WorkflowStepPage } from "@/features/workflow/components/WorkflowStepPage";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import { appRoutes } from "@/shared/constants/appRoutes";
import { getReviewState } from "../api";
import type { ReviewItem } from "../types";
import { ReviewViewTabs } from "./ReviewViewTabs";

type ElementCategory = ReviewItem["entity_type"];

type TypeGroup = {
  key: string;
  code: string;
  elementType: ElementCategory;
  label: string;
  measure: string;
  material: string;
  floorNames: string[];
  items: ReviewItem[];
  confirmed: number;
  needsReview: number;
  totalAreaM2: number | null;
};

const categoryOptions: Array<{ value: ElementCategory; label: string }> = [
  { value: "door", label: "Doors" },
  { value: "window", label: "Windows" },
  { value: "wall", label: "Walls" },
  { value: "floor", label: "Floors" },
];

function text(value: unknown): string {
  return value == null ? "" : String(value).trim();
}

function number(value: unknown): number | null {
  if (value == null || String(value).trim() === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function cleanCode(value: unknown): string {
  const result = text(value);
  return result ? result.toUpperCase() : "";
}

function groupCode(item: ReviewItem): string {
  if (item.entity_type === "door" || item.entity_type === "window") {
    return cleanCode(item.data.type_code || item.data.drawing_tag) || "UNCLASSIFIED";
  }

  if (item.entity_type === "wall") {
    const explicit = cleanCode(item.data.wall_type);
    const classification = cleanCode(item.data.classification);
    const thickness = number(item.data.thickness_mm);
    if (explicit && /^[A-Z]{1,4}[- ]?\d+[A-Z]?$/.test(explicit)) return explicit;
    const parts = [classification, thickness ? `${thickness}MM` : "", explicit].filter(Boolean);
    return parts.length ? parts.join(" ") : "UNCLASSIFIED";
  }

  return (
    cleanCode(item.data.floor_type_code) ||
    cleanCode(item.data.floor_finish) ||
    cleanCode(item.data.room_type) ||
    "UNCLASSIFIED"
  );
}

function groupLabel(item: ReviewItem, code: string): string {
  if (item.entity_type === "door") return code === "UNCLASSIFIED" ? "Door type not assigned" : `${code} doors`;
  if (item.entity_type === "window") return code === "UNCLASSIFIED" ? "Window type not assigned" : `${code} windows`;
  if (item.entity_type === "wall") {
    return (
      text(item.data.wall_type) ||
      [text(item.data.classification), number(item.data.thickness_mm) ? `${number(item.data.thickness_mm)} mm` : ""]
        .filter(Boolean)
        .join(" · ") ||
      "Wall type not assigned"
    );
  }
  return text(item.data.floor_finish) || text(item.data.room_type) || "Floor finish not assigned";
}

function openingMeasure(item: ReviewItem): string {
  const width = number(item.data.width_mm);
  const height = number(item.data.height_mm);
  return width && height ? `${width} × ${height} mm` : "Size needs review";
}

function wallMeasure(item: ReviewItem): string {
  const thickness = number(item.data.thickness_mm);
  const classification = text(item.data.classification);
  return [thickness ? `${thickness} mm thick` : "Thickness needs review", classification]
    .filter(Boolean)
    .join(" · ");
}

function floorMeasure(item: ReviewItem): string {
  const area = number(item.data.area_m2);
  return area ? `${area.toFixed(2)} m²` : "Area needs review";
}

function itemMeasure(item: ReviewItem): string {
  if (item.entity_type === "door" || item.entity_type === "window") return openingMeasure(item);
  if (item.entity_type === "wall") return wallMeasure(item);
  return floorMeasure(item);
}

function groupMeasure(items: ReviewItem[]): string {
  const measures = [...new Set(items.map(itemMeasure).filter(Boolean))];
  if (!measures.length) return "—";
  return measures.length === 1 ? measures[0] : "Mixed sizes / measures";
}

function groupMaterial(items: ReviewItem[]): string {
  const values = [
    ...new Set(
      items
        .map((item) => {
          if (item.entity_type === "door" || item.entity_type === "window") {
            return text(item.data.material || item.data.frame_material || item.data.finish);
          }
          if (item.entity_type === "wall") {
            return text(item.data.wall_type || item.data.side_1_finish || item.data.side_2_finish);
          }
          return text(item.data.floor_finish);
        })
        .filter(Boolean),
    ),
  ];
  if (!values.length) return "—";
  return values.length === 1 ? values[0] : "Mixed materials / finishes";
}

function areaTotal(items: ReviewItem[]): number | null {
  if (!items.length || !["wall", "floor"].includes(items[0].entity_type)) return null;
  return items.reduce((sum, item) => {
    const value = item.entity_type === "wall" ? number(item.data.net_area_m2) : number(item.data.area_m2);
    return sum + (value || 0);
  }, 0);
}

function buildGroups(items: ReviewItem[], category: ElementCategory): TypeGroup[] {
  const map = new Map<string, ReviewItem[]>();
  items
    .filter((item) => item.entity_type === category)
    .forEach((item) => {
      const code = groupCode(item);
      const key = `${category}:${code}`;
      map.set(key, [...(map.get(key) || []), item]);
    });

  return [...map.entries()]
    .map(([key, groupedItems]) => {
      const first = groupedItems[0];
      const code = groupCode(first);
      return {
        key,
        code,
        elementType: category,
        label: groupLabel(first, code),
        measure: groupMeasure(groupedItems),
        material: groupMaterial(groupedItems),
        floorNames: [...new Set(groupedItems.map((item) => text(item.data.floor)).filter(Boolean))],
        items: groupedItems,
        confirmed: groupedItems.filter((item) => item.status === "confirmed").length,
        needsReview: groupedItems.filter((item) => item.status === "needs_review").length,
        totalAreaM2: areaTotal(groupedItems),
      };
    })
    .sort((left, right) => {
      if (left.code === "UNCLASSIFIED") return 1;
      if (right.code === "UNCLASSIFIED") return -1;
      return left.code.localeCompare(right.code, undefined, { numeric: true });
    });
}

function categoryLabel(category: ElementCategory): string {
  return categoryOptions.find((item) => item.value === category)?.label || category;
}

function statusClass(needsReview: number): string {
  return needsReview
    ? "border-amber-200 bg-amber-50 text-amber-700"
    : "border-emerald-200 bg-emerald-50 text-emerald-700";
}

export function ReviewClassificationPage({ projectId }: { projectId: string }) {
  const [category, setCategory] = useState<ElementCategory>("door");
  const [floorId, setFloorId] = useState<string>("");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["review", projectId, floorId || null, "classification-summary"],
    queryFn: () => getReviewState(projectId, floorId || null, "all"),
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    staleTime: 60 * 60_000,
    placeholderData: (previous) => previous,
    refetchInterval: (result) => result.state.data?.active_jobs?.length ? 2500 : false,
  });

  const state = query.data;
  const groups = useMemo(() => buildGroups(state?.items || [], category), [category, state?.items]);
  const selected = groups.find((group) => group.key === selectedKey) || groups[0] || null;

  const categoryStats = useMemo(() => {
    const items = state?.items || [];
    return Object.fromEntries(
      categoryOptions.map((option) => {
        const categoryItems = items.filter((item) => item.entity_type === option.value);
        return [
          option.value,
          {
            items: categoryItems.length,
            groups: buildGroups(items, option.value).length,
            needsReview: categoryItems.filter((item) => item.status === "needs_review").length,
          },
        ];
      }),
    ) as Record<ElementCategory, { items: number; groups: number; needsReview: number }>;
  }, [state?.items]);

  function chooseCategory(next: ElementCategory) {
    setCategory(next);
    setSelectedKey(null);
  }

  function chooseFloor(next: string) {
    setFloorId(next);
    setSelectedKey(null);
  }

  return (
    <WorkflowStepPage projectId={projectId} stepKey="review">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-5 py-3">
        <ReviewViewTabs projectId={projectId} active="types" />
        <select
          value={floorId}
          onChange={(event) => chooseFloor(event.target.value)}
          className="h-10 min-w-[180px] rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 outline-none focus:border-blue-400"
        >
          <option value="">All floors</option>
          {state?.floors.map((floor) => (
            <option key={floor.id} value={floor.id}>
              {floor.name}
            </option>
          ))}
        </select>
      </div>

      <div className="border-b border-slate-200 bg-white px-5 py-4">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {categoryOptions.map((option) => {
            const stats = categoryStats[option.value];
            const active = category === option.value;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => chooseCategory(option.value)}
                className={
                  active
                    ? "rounded-xl border border-blue-300 bg-blue-50 px-4 py-3 text-left ring-2 ring-blue-100"
                    : "rounded-xl border border-slate-200 bg-white px-4 py-3 text-left hover:border-blue-200 hover:bg-slate-50"
                }
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{option.label}</p>
                  {stats.needsReview ? (
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-700">
                      {stats.needsReview} review
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 text-2xl font-semibold text-slate-950">{stats.items}</p>
                <p className="mt-1 text-xs text-slate-500">{stats.groups} classifications</p>
              </button>
            );
          })}
        </div>
      </div>

      {query.error ? (
        <div className="p-5">
          <ErrorMessage message={query.error.message} />
        </div>
      ) : null}

      <div className="grid min-h-[620px] grid-cols-[minmax(0,1fr)_330px] overflow-hidden bg-white">
        <main className="min-w-0 border-r border-slate-200">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <div>
              <h3 className="text-base font-semibold text-slate-950">{categoryLabel(category)} by type</h3>
              <p className="mt-0.5 text-xs text-slate-500">
                {groups.length} classifications · {categoryStats[category].items} items
              </p>
            </div>
          </div>

          <div className="max-h-[620px] overflow-auto">
            <table className="w-full border-collapse text-left text-sm">
              <thead className="sticky top-0 z-10 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3">Type</th>
                  <th className="px-5 py-3">Size / classification</th>
                  <th className="px-5 py-3">Material / finish</th>
                  <th className="px-5 py-3">Floors</th>
                  <th className="px-5 py-3 text-right">Qty</th>
                  <th className="px-5 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((group) => (
                  <tr
                    key={group.key}
                    onClick={() => setSelectedKey(group.key)}
                    className={
                      selected?.key === group.key
                        ? "cursor-pointer border-t border-slate-200 bg-blue-50"
                        : "cursor-pointer border-t border-slate-200 hover:bg-slate-50"
                    }
                  >
                    <td className="px-5 py-4">
                      <p className={group.code === "UNCLASSIFIED" ? "font-semibold text-amber-700" : "font-semibold text-slate-950"}>
                        {group.code === "UNCLASSIFIED" ? "Not classified" : group.code}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">{group.label}</p>
                    </td>
                    <td className="px-5 py-4 font-medium text-slate-700">{group.measure}</td>
                    <td className="px-5 py-4 text-slate-600">{group.material}</td>
                    <td className="px-5 py-4 text-slate-600">{group.floorNames.join(", ") || "—"}</td>
                    <td className="px-5 py-4 text-right">
                      <p className="font-semibold text-slate-950">{group.items.length}</p>
                      {group.totalAreaM2 != null ? (
                        <p className="mt-1 text-xs text-slate-500">{group.totalAreaM2.toFixed(2)} m²</p>
                      ) : null}
                    </td>
                    <td className="px-5 py-4">
                      <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${statusClass(group.needsReview)}`}>
                        {group.needsReview ? `${group.needsReview} need review` : "Confirmed"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {!query.isPending && !groups.length ? (
              <div className="p-12 text-center text-sm text-slate-500">
                No {categoryLabel(category).toLowerCase()} are available for this floor selection.
              </div>
            ) : null}
          </div>
        </main>

        <aside className="max-h-[680px] overflow-y-auto bg-white p-5">
          {selected ? (
            <div>
              <p className="text-xs font-semibold uppercase tracking-[.14em] text-slate-400">Selected classification</p>
              <h3 className="mt-1 text-xl font-semibold text-slate-950">
                {selected.code === "UNCLASSIFIED" ? "Not classified" : selected.code}
              </h3>
              <p className="mt-1 text-sm text-slate-500">{selected.label}</p>

              <div className="mt-4 grid grid-cols-2 gap-2">
                <MiniStat label="Items" value={selected.items.length} />
                <MiniStat label="Need review" value={selected.needsReview} tone={selected.needsReview ? "amber" : "slate"} />
              </div>

              <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
                <DetailRow label="Measure" value={selected.measure} />
                <DetailRow label="Material / finish" value={selected.material} />
                <DetailRow label="Floors" value={selected.floorNames.join(", ") || "—"} />
                {selected.totalAreaM2 != null ? <DetailRow label="Total area" value={`${selected.totalAreaM2.toFixed(2)} m²`} /> : null}
              </div>

              <div className="mt-5">
                <p className="text-xs font-semibold uppercase tracking-[.14em] text-slate-400">Items in this type</p>
                <div className="mt-2 space-y-2">
                  {selected.items.map((item) => (
                    <div key={item.id} className="rounded-xl border border-slate-200 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-slate-900">{item.display_number || item.title}</p>
                          <p className="mt-1 text-xs text-slate-500">{text(item.data.floor)} · {itemMeasure(item)}</p>
                        </div>
                        <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${statusClass(item.status === "needs_review" ? 1 : 0)}`}>
                          {item.status === "needs_review" ? "Review" : "Confirmed"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <Link
                href={appRoutes.workflowStep(projectId, "review")}
                className="mt-5 inline-flex h-10 w-full items-center justify-center rounded-lg border border-slate-200 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                Open detailed review
              </Link>
            </div>
          ) : (
            <p className="text-sm text-slate-500">Select a classification to see its items.</p>
          )}
        </aside>
      </div>

      <div className="flex items-center justify-between border-t border-slate-200 bg-white px-6 py-4">
        <Link
          className="inline-flex h-11 items-center rounded-xl border border-slate-200 px-5 text-sm font-semibold text-slate-700"
          href={appRoutes.workflowStep(projectId, "review")}
        >
          Back to detailed review
        </Link>
        <Link
          className="inline-flex h-11 items-center rounded-xl bg-blue-600 px-5 text-sm font-semibold text-white"
          href={appRoutes.workflowStep(projectId, "boq")}
        >
          Continue to BOQ
        </Link>
      </div>
    </WorkflowStepPage>
  );
}

function MiniStat({
  label,
  value,
  tone = "slate",
}: {
  label: string;
  value: number;
  tone?: "slate" | "amber";
}) {
  return (
    <div className={tone === "amber" ? "rounded-xl bg-amber-50 p-3 text-amber-800" : "rounded-xl bg-slate-50 p-3 text-slate-800"}>
      <p className="text-[11px] font-semibold uppercase tracking-wide opacity-65">{label}</p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="mt-2 first:mt-0">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-0.5 font-semibold text-slate-800">{value}</p>
    </div>
  );
}
