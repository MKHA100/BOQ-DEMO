"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/shared/components/Button";
import type { BoqPlaceholder, BoqTemplateItem } from "../types";
import { BoqAdvancedTemplateSettings } from "./BoqAdvancedTemplateSettings";
import { PlaceholderPicker } from "./PlaceholderPicker";
import { TemplatePreview } from "./TemplatePreview";

const defaults: Record<BoqTemplateItem["element_type"], Omit<BoqTemplateItem, "id" | "template_id">> = {
  door: { name: "Doors", element_type: "door", section_code: "5D", section_name: "Doors", unit: "nr", description_template: "[TYPE_CODE] – [MATERIAL] door, size [WIDTH] × [HEIGHT] mm, including [FRAME_MATERIAL] frame and [FINISH].", keywords: [], template_mode: "standard", conditional_rules: [], formula: { type: "quantity_x_rate" }, sort_order: 100, is_active: true },
  window: { name: "Windows", element_type: "window", section_code: "5E", section_name: "Windows", unit: "nr", description_template: "[TYPE_CODE] – [FRAME_MATERIAL] framed window, size [WIDTH] × [HEIGHT] mm, including [GLASS_TYPE] glazing and [FINISH].", keywords: [], template_mode: "standard", conditional_rules: [], formula: { type: "quantity_x_rate" }, sort_order: 200, is_active: true },
  wall_external: { name: "External walls", element_type: "wall_external", section_code: "5A", section_name: "External walls", unit: "m²", description_template: "[THICKNESS] mm thick [MATERIAL] external wall, including [SIDE_1_FINISH] and [SIDE_2_FINISH].", keywords: [], template_mode: "standard", conditional_rules: [], formula: { type: "quantity_x_rate" }, sort_order: 300, is_active: true },
  wall_internal: { name: "Internal walls", element_type: "wall_internal", section_code: "5B", section_name: "Internal walls", unit: "m²", description_template: "[THICKNESS] mm thick [MATERIAL] internal wall, including [SIDE_1_FINISH] and [SIDE_2_FINISH].", keywords: [], template_mode: "standard", conditional_rules: [], formula: { type: "quantity_x_rate" }, sort_order: 400, is_active: true },
  floor: { name: "Floor finishes", element_type: "floor", section_code: "5J", section_name: "Floor finishes", unit: "m²", description_template: "[FLOOR_FINISH] floor finish to [ROOM_NAME] on [FLOOR_NAMES].", keywords: [], template_mode: "standard", conditional_rules: [], formula: { type: "quantity_x_rate" }, sort_order: 500, is_active: true },
  manual: { name: "Manual items", element_type: "manual", section_code: "9Z", section_name: "Other items", unit: "item", description_template: "Manual BOQ item", keywords: [], template_mode: "standard", conditional_rules: [], formula: { type: "quantity_x_rate" }, sort_order: 900, is_active: true },
};

function fromItem(item: BoqTemplateItem | null, elementType: BoqTemplateItem["element_type"]): Omit<BoqTemplateItem, "id" | "template_id"> {
  if (!item) return { ...defaults[elementType], conditional_rules: [], keywords: [], formula: { ...defaults[elementType].formula } };
  return {
    name: item.name,
    element_type: item.element_type,
    section_code: item.section_code,
    section_name: item.section_name,
    unit: item.unit,
    description_template: item.description_template,
    keywords: [...item.keywords],
    template_mode: item.template_mode,
    conditional_rules: Array.isArray(item.conditional_rules) ? item.conditional_rules.map((rule) => ({ ...rule })) : { branches: item.conditional_rules.branches.map((branch) => ({ ...branch, conditions: branch.conditions.map((condition) => ({ ...condition })), output: { ...branch.output, amount_formula: { ...branch.output.amount_formula, variables: [...branch.output.amount_formula.variables] } } })) },
    formula: { ...item.formula },
    sort_order: item.sort_order,
    is_active: item.is_active,
  };
}

function localPreview(template: string, placeholders: BoqPlaceholder[]) {
  let result = template;
  for (const placeholder of placeholders) result = result.replaceAll(`[${placeholder.key}]`, placeholder.example || placeholder.label);
  return result;
}

export function BoqTemplateEditor({
  item,
  initialElementType,
  placeholders,
  serverPreview,
  saving,
  onSave,
  onDelete,
  onPreview,
}: {
  item: BoqTemplateItem | null;
  initialElementType: BoqTemplateItem["element_type"];
  placeholders: BoqPlaceholder[];
  serverPreview: string;
  saving: boolean;
  onSave: (payload: Omit<BoqTemplateItem, "id" | "template_id">) => Promise<void>;
  onDelete?: () => Promise<void>;
  onPreview: () => Promise<void>;
}) {
  const [form, setForm] = useState(() => fromItem(item, initialElementType));
  const [advanced, setAdvanced] = useState(false);
  const textarea = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    setForm(fromItem(item, initialElementType));
    setAdvanced(false);
  }, [initialElementType, item]);

  const preview = useMemo(() => serverPreview || localPreview(form.description_template, placeholders), [form.description_template, placeholders, serverPreview]);

  function insertToken(token: string) {
    const node = textarea.current;
    const start = node?.selectionStart ?? form.description_template.length;
    const end = node?.selectionEnd ?? start;
    setForm({ ...form, description_template: `${form.description_template.slice(0, start)}${token}${form.description_template.slice(end)}` });
    window.setTimeout(() => node?.focus(), 0);
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Template name" value={form.name} onChange={(value) => setForm({ ...form, name: value })} />
        <label>
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Element type</span>
          <select className="input mt-2 w-full" value={form.element_type} onChange={(event) => {
            const elementType = event.target.value as BoqTemplateItem["element_type"];
            setForm({ ...defaults[elementType] });
          }}>
            <option value="door">Door</option>
            <option value="window">Window</option>
            <option value="wall_external">External wall</option>
            <option value="wall_internal">Internal wall</option>
            <option value="floor">Floor finish</option>
            <option value="manual">Manual item</option>
          </select>
        </label>
        <Field label="Section" value={form.section_name} onChange={(value) => setForm({ ...form, section_name: value })} />
        <div className="grid grid-cols-[1fr_120px] gap-3">
          <Field label="Section code" value={form.section_code || ""} onChange={(value) => setForm({ ...form, section_code: value })} />
          <Field label="Unit" value={form.unit} onChange={(value) => setForm({ ...form, unit: value })} />
        </div>
      </div>

      <label className="block">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Description</span>
        <textarea ref={textarea} className="input mt-2 min-h-36 w-full resize-y text-sm leading-6" value={form.description_template} onChange={(event) => setForm({ ...form, description_template: event.target.value })} />
      </label>

      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Insert project data</p>
        <div className="mt-2"><PlaceholderPicker placeholders={placeholders} onPick={insertToken} /></div>
      </div>

      <TemplatePreview description={preview} />

      <section className="border-t border-slate-200 pt-5">
        <button type="button" className="flex w-full items-center justify-between text-left" onClick={() => setAdvanced((value) => !value)}>
          <span>
            <span className="block text-sm font-semibold text-slate-900">Advanced template rules</span>
            <span className="mt-1 block text-xs text-slate-500">Conditions, keywords, sort order and activation.</span>
          </span>
          <span className="text-lg text-slate-400">{advanced ? "−" : "+"}</span>
        </button>
        {advanced ? <div className="mt-4"><BoqAdvancedTemplateSettings value={form} placeholders={placeholders} onChange={setForm} /></div> : null}
      </section>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-5">
        <div>{onDelete ? <Button variant="danger" disabled={saving} onClick={() => void onDelete()}>Delete item</Button> : null}</div>
        <div className="flex gap-2">
          <Button variant="secondary" disabled={saving || !item} onClick={() => void onPreview()}>Refresh preview</Button>
          <Button disabled={saving || !form.name.trim() || !form.description_template.trim()} onClick={() => void onSave(form)}>{saving ? "Saving…" : item ? "Save template" : "Create template"}</Button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label><span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span><input className="input mt-2 w-full" value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}
