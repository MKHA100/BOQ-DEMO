"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/shared/components/Button";
import type { ReviewElement, ScheduleEntry } from "../types";

function resolvedValue(element: ReviewElement, name: string): string {
  const value = element.resolved_data?.[name]
    ?? element.properties.find((property) => property.property_name === name)?.value;
  return value == null ? "" : String(value);
}

function sourceLabel(value?: string): string {
  return ({
    user_confirmed: "Confirmed",
    schedule: "Schedule",
    specification: "Specification",
    drawing_note: "Drawing detail",
    model: "Model",
    calculated: "Calculated",
    default: "Default",
    saved: "Saved",
  } as Record<string, string>)[value || ""] || "Saved";
}

const statusTone = {
  ready: "border-blue-200 bg-blue-50 text-blue-700",
  needs_review: "border-amber-200 bg-amber-50 text-amber-700",
  confirmed: "border-emerald-200 bg-emerald-50 text-emerald-700",
} as const;

export function ElementInspector({
  element,
  schedules,
  saving,
  editingGeometry,
  onToggleGeometryEdit,
  onPatch,
  onProperty,
  onSchedule,
}: {
  element: ReviewElement | null;
  schedules: ScheduleEntry[];
  saving: boolean;
  editingGeometry: boolean;
  onToggleGeometryEdit: () => void;
  onPatch: (patch: Record<string, unknown>) => Promise<void>;
  onProperty: (name: string, value: unknown, unit?: string | null) => Promise<void>;
  onSchedule: (entryId: string) => Promise<void>;
}) {
  const [typeCode, setTypeCode] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!element) return;
    setTypeCode(String(element.resolved_data?.type_code || element.type_code || element.tag_text || ""));
    setValues({
      width_mm: resolvedValue(element, "width_mm"),
      height_mm: resolvedValue(element, "height_mm"),
      material: resolvedValue(element, "material"),
      frame_material: resolvedValue(element, "frame_material"),
      finish: resolvedValue(element, "finish"),
      glass_type: resolvedValue(element, "glass_type"),
      fire_rating: resolvedValue(element, "fire_rating"),
    });
  }, [element]);

  const available = useMemo(
    () => schedules.filter((entry) => entry.category === element?.element_type),
    [element?.element_type, schedules],
  );

  if (!element) {
    return (
      <div className="flex h-full min-h-72 items-center justify-center p-6 text-center">
        <div>
          <p className="text-sm font-semibold text-slate-700">No item selected</p>
          <p className="mt-1 text-sm text-slate-500">Select an item number from the plan or the item list.</p>
        </div>
      </div>
    );
  }

  const isWall = element.element_type === "wall";
  const fields = isWall
    ? [{ key: "material", label: "Material" }]
    : [
        { key: "width_mm", label: "Width", unit: "mm" },
        { key: "height_mm", label: "Height", unit: "mm" },
        { key: "material", label: "Material" },
        { key: "frame_material", label: "Frame material" },
        { key: "finish", label: "Finish" },
        ...(element.element_type === "window" ? [{ key: "glass_type", label: "Glass type" }] : []),
        ...(element.element_type === "door" ? [{ key: "fire_rating", label: "Fire rating" }] : []),
      ];

  const sourceFor = (field: string) => sourceLabel(element.resolved_sources?.[field]);

  return (
    <div className="space-y-5 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Selected item</p>
          <h3 className="mt-1 text-xl font-semibold text-slate-950">{element.display_number}</h3>
          <p className="mt-1 text-sm capitalize text-slate-500">{element.element_type}</p>
        </div>
        <span className={`rounded-lg border px-2 py-1 text-xs font-semibold capitalize ${statusTone[element.status]}`}>
          {element.status === "confirmed" && !element.user_confirmed ? "System checked" : element.status.replace("_", " ")}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
        <div>
          <p className="text-xs text-slate-500">Drawing tag</p>
          <p className="mt-1 font-semibold text-slate-900">{element.tag_text || "—"}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Type code</p>
          <p className="mt-1 font-semibold text-slate-900">{element.resolved_data?.type_code as string || element.type_code || "—"}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Size</p>
          <p className="mt-1 font-semibold text-slate-900">
            {values.width_mm && values.height_mm ? `${values.width_mm} × ${values.height_mm} mm` : "—"}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Detail source</p>
          <p className="mt-1 font-semibold text-slate-900">
            {element.schedule_match ? "Schedule" : element.drawing_detail ? "Drawing detail" : "Model"}
          </p>
        </div>
      </div>

      {element.detail_missing_fields?.length ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-600">
          Optional details not found: {element.detail_missing_fields.map((field) => field.replaceAll("_", " ")).join(", ")}. Detection can still be used.
        </div>
      ) : null}

      <Button variant={editingGeometry ? "primary" : "secondary"} className="w-full" onClick={onToggleGeometryEdit}>
        {editingGeometry ? "Finish box adjustment" : "Adjust detection box"}
      </Button>

      <label className="block">
        <span className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Type code</span>
        <div className="mt-2 flex items-center gap-2">
          <input
            className="input"
            value={typeCode}
            onChange={(event) => setTypeCode(event.target.value)}
            onBlur={() => {
              const current = String(element.type_code || "");
              if (typeCode.trim() !== current) void onPatch({ type_code: typeCode.trim() });
            }}
          />
          <span className="whitespace-nowrap rounded-lg bg-slate-100 px-2 py-2 text-[11px] font-medium text-slate-500">
            {sourceFor("type_code")}
          </span>
        </div>
      </label>

      {available.length ? (
        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Schedule assignment</span>
          <select
            className="input mt-2"
            value={element.assigned_schedule_entry_id || ""}
            onChange={(event) => event.target.value && void onSchedule(event.target.value)}
          >
            <option value="">Automatic / drawing detail</option>
            {available.map((entry) => (
              <option key={entry.id} value={entry.id}>{String(entry.data.type_code || entry.entity_key)}</option>
            ))}
          </select>
        </label>
      ) : null}

      {fields.map((field) => (
        <label key={field.key} className="block">
          <span className="flex items-center justify-between gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
            <span>{field.label}</span>
            <span className="normal-case tracking-normal text-slate-400">{sourceFor(field.key)}</span>
          </span>
          <div className="mt-2 flex gap-2">
            <input
              className="input"
              value={values[field.key] || ""}
              onChange={(event) => setValues((current) => ({ ...current, [field.key]: event.target.value }))}
              onBlur={() => {
                const current = resolvedValue(element, field.key);
                if ((values[field.key] || "") === current) return;
                const next = field.unit ? Number(values[field.key]) : values[field.key];
                void onProperty(field.key, next, field.unit);
              }}
            />
            {field.unit ? <span className="flex h-11 items-center rounded-xl bg-slate-100 px-3 text-sm text-slate-500">{field.unit}</span> : null}
          </div>
        </label>
      ))}

      <div className="rounded-xl bg-slate-50 p-4 text-sm">
        <div className="flex justify-between"><span className="text-slate-500">Detection source</span><strong className="capitalize text-slate-900">{element.source}</strong></div>
        <div className="mt-2 flex justify-between">
          <span className="text-slate-500">Approval</span>
          <strong className="text-slate-900">
            {element.user_confirmed ? "User approved" : element.status === "confirmed" ? "System checked" : "Review needed"}
          </strong>
        </div>
        {element.confidence != null ? <div className="mt-2 flex justify-between"><span className="text-slate-500">Confidence</span><strong className="text-slate-900">{Math.round(element.confidence * 100)}%</strong></div> : null}
      </div>

      <div className="grid grid-cols-2 gap-2">
        <Button variant="secondary" disabled={saving} onClick={() => void onPatch({ excluded: !element.excluded })}>
          {element.excluded ? "Restore" : "Exclude"}
        </Button>
        <Button disabled={saving || element.status === "confirmed"} onClick={() => void onPatch({ review_status: "confirmed" })}>
          {element.status === "confirmed" ? "System checked" : "Confirm"}
        </Button>
      </div>
    </div>
  );
}
