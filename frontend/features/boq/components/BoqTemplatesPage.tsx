"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/shared/components/Button";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import { LoadingState } from "@/shared/components/LoadingState";
import { appRoutes } from "@/shared/constants/appRoutes";
import {
  createBoqTemplateItem,
  createBoqTemplatePackage,
  deleteBoqTemplateItem,
  duplicateBoqTemplatePackage,
  getBoqTemplateLibrary,
  selectBoqTemplate,
  updateBoqTemplateItem,
  updateBoqTemplatePackage,
} from "../api";
import type {
  BoqAmountFormula,
  BoqConditionalBranch,
  BoqConditionalRule,
  BoqConditionalRules,
  BoqTemplateItem,
  BoqTemplateMode,
  BoqTemplatePackage,
} from "../types";
import { useBoqJob } from "../hooks/useBoqJob";
import { BoqShell } from "./BoqShell";
import { ConditionalRuleBuilder, normalizeRules } from "./ConditionalRuleBuilder";
import { FormulaBuilder, normalizeFormula } from "./FormulaBuilder";

type ElementType = BoqTemplateItem["element_type"];
type ItemDraft = Omit<BoqTemplateItem, "id" | "template_id"> & { id?: string; template_id?: string };
type BoqSectionOption = { key: string; label: string; section_code: string | null; section_name: string };
type ElementDefault = {
  name: string;
  unit: string;
  description_template: string;
  keywords: string[];
  section_code: string | null;
  section_name: string;
  formula: BoqAmountFormula;
};

const boqSectionOptions: BoqSectionOption[] = [
  { key: "masonry-external", label: "14A: External masonry", section_code: "14A", section_name: "Masonry – external walls" },
  { key: "masonry-internal", label: "14B: Internal masonry", section_code: "14B", section_name: "Masonry – internal walls" },
  { key: "windows", label: "23: Windows", section_code: "23", section_name: "Windows, screens and lights" },
  { key: "doors", label: "24: Doors", section_code: "24", section_name: "Doors, shutters and hatches" },
  { key: "finishes", label: "28: Floor finishes", section_code: "28", section_name: "Ceiling, wall and floor finishes" },
  { key: "general", label: "General", section_code: null, section_name: "Other items" },
];

const elementDefaults: Record<ElementType, ElementDefault> = {
  wall_external: {
    name: "External Wall Template", unit: "m²", section_code: "14A", section_name: "Masonry – external walls",
    description_template: "[THICKNESS] mm thick [MATERIAL] external wall, including [SIDE_1_FINISH] and [SIDE_2_FINISH].",
    keywords: ["external", "wall", "masonry", "brick", "block"], formula: { operation: "value", variables: ["Quantity"], constant: null },
  },
  wall_internal: {
    name: "Internal Wall Template", unit: "m²", section_code: "14B", section_name: "Masonry – internal walls",
    description_template: "[THICKNESS] mm thick [MATERIAL] internal wall, including [SIDE_1_FINISH] and [SIDE_2_FINISH].",
    keywords: ["internal", "wall", "partition", "masonry"], formula: { operation: "value", variables: ["Quantity"], constant: null },
  },
  door: {
    name: "Door Template", unit: "nr", section_code: "24", section_name: "Doors, shutters and hatches",
    description_template: "[TYPE_CODE] – [MATERIAL] door size [WIDTH] × [HEIGHT] mm, including [FRAME_MATERIAL] frame and [FINISH].",
    keywords: ["door", "doorset", "opening", "frame"], formula: { operation: "value", variables: ["Quantity"], constant: null },
  },
  window: {
    name: "Window Template", unit: "nr", section_code: "23", section_name: "Windows, screens and lights",
    description_template: "[TYPE_CODE] – [FRAME_MATERIAL] framed window size [WIDTH] × [HEIGHT] mm, glazed with [GLASS_TYPE] and finished [FINISH].",
    keywords: ["window", "glazing", "glass", "frame"], formula: { operation: "value", variables: ["Quantity"], constant: null },
  },
  floor: {
    name: "Floor Finish Template", unit: "m²", section_code: "28", section_name: "Ceiling, wall and floor finishes",
    description_template: "Provide and lay [FLOOR_FINISH] floor finish to [ROOM_NAME], including preparation and completion.",
    keywords: ["floor", "finish", "flooring", "tile", "screed"], formula: { operation: "value", variables: ["Quantity"], constant: null },
  },
  manual: {
    name: "General Item Template", unit: "Item", section_code: null, section_name: "Other items",
    description_template: "[DESCRIPTION]", keywords: [], formula: { operation: "value", variables: ["Quantity"], constant: null },
  },
};

const elementTypeOptions: ElementType[] = ["wall_external", "wall_internal", "door", "window", "floor", "manual"];
const defaultItems: ItemDraft[] = [
  createItemForType("wall_external"), createItemForType("wall_internal"), createItemForType("door"),
  createItemForType("window"), createItemForType("floor"), createItemForType("manual"),
];

export function BoqTemplatesPage({ projectId }: { projectId: string }) {
  const query = useQuery({ queryKey: ["boq", projectId, "templates"], queryFn: () => getBoqTemplateLibrary(projectId), refetchOnWindowFocus: false });
  const { run, saving, error: jobError } = useBoqJob(projectId);
  const [activePackage, setActivePackage] = useState<BoqTemplatePackage | null>(null);
  const [name, setName] = useState("Project BOQ Template Set");
  const [items, setItems] = useState<ItemDraft[]>(() => cloneItems(defaultItems));
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [itemDraft, setItemDraft] = useState<ItemDraft | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  const activeItems = useMemo(() => items.filter((item) => item.is_active !== false), [items]);
  const conditionalRuleCount = useMemo(() => items.filter((item) => item.template_mode === "conditional" && normalizeItemRules(item).branches.length > 0).length, [items]);
  const itemPreview = useMemo(() => itemDraft ? renderPreview(itemDraft) : "", [itemDraft]);

  useEffect(() => {
    if (!query.data) return;
    const selected = query.data.packages.find((item) => item.id === query.data.selected_template_id) || query.data.packages[0] || null;
    if (selected) loadPackageIntoForm(selected); else resetToNewProjectPackage();
  }, [query.data]);

  function loadPackageIntoForm(record: BoqTemplatePackage) {
    setActivePackage(record);
    setName(record.name || "Project BOQ Template Set");
    setItems(record.items.length ? record.items.map(toDraft) : cloneItems(defaultItems));
    closeItemForm(); setMessage(null); setLocalError(null);
  }

  function resetToNewProjectPackage() {
    setActivePackage(null); setName("Project BOQ Template Set"); setItems(cloneItems(defaultItems)); closeItemForm(); setMessage(null); setLocalError(null);
  }

  function openNewItem() { setEditingIndex(null); setItemDraft(createItemForType("manual", `Template ${items.length + 1}`)); setMessage(null); setLocalError(null); }
  function openEditItem(index: number) { const item = items[index]; if (!item) return; setEditingIndex(index); setItemDraft(cloneItem(item)); setMessage(null); setLocalError(null); }
  function closeItemForm() { setEditingIndex(null); setItemDraft(null); }
  function updateItemDraft(patch: Partial<ItemDraft>) { setItemDraft((current) => current ? normalizeItem({ ...current, ...patch }, editingIndex ?? items.length) : current); }

  function updateItemDraftElementType(elementType: ElementType) {
    setItemDraft((current) => {
      if (!current) return current;
      const defaults = elementDefaults[elementType];
      const mode = current.template_mode || "standard";
      return normalizeItem({
        ...current, element_type: elementType, name: defaults.name, unit: defaults.unit,
        description_template: defaults.description_template, keywords: defaults.keywords,
        section_code: defaults.section_code, section_name: defaults.section_name, formula: defaults.formula,
        template_mode: mode,
        conditional_rules: mode === "conditional" ? defaultConditionalRulesForType(elementType) : current.conditional_rules,
      }, editingIndex ?? items.length);
    });
  }

  function updateItemDraftBoqSection(sectionKey: string) {
    const section = boqSectionOptions.find((item) => item.key === sectionKey) || boqSectionOptions[boqSectionOptions.length - 1];
    updateItemDraft({ section_code: section.section_code, section_name: section.section_name });
  }

  function updateItemDraftMode(templateMode: BoqTemplateMode) {
    setItemDraft((current) => current ? normalizeItem({
      ...current, template_mode: templateMode,
      conditional_rules: templateMode === "conditional" ? normalizeItemRules(current) : current.conditional_rules,
    }, editingIndex ?? items.length) : current);
  }

  function saveItemDraft() {
    if (!itemDraft) return;
    if (!itemDraft.name.trim()) { setLocalError("Template name is required."); return; }
    if (itemDraft.template_mode === "conditional") {
      if (!normalizeItemRules(itemDraft).branches.length) { setLocalError("Add at least one conditional branch."); return; }
    } else if (!itemDraft.description_template.trim()) { setLocalError("Description template is required."); return; }
    const normalized = normalizeItem(itemDraft, editingIndex ?? items.length);
    setItems((current) => editingIndex === null ? [...current, normalized] : current.map((item, index) => index === editingIndex ? normalized : item));
    closeItemForm(); setMessage("Template saved. Click Save Templates to apply it to the project."); setLocalError(null);
  }

  function removeItem(index: number) {
    if (items.length <= 1) { setLocalError("At least one template is required."); return; }
    setItems((current) => current.filter((_, itemIndex) => itemIndex !== index)); closeItemForm(); setMessage("Template removed. Click Save Templates to apply the change."); setLocalError(null);
  }

  function toggleItemStatus(index: number) { setItems((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, is_active: item.is_active === false } : item)); }

  async function saveTemplateSet() {
    if (itemDraft) { setLocalError("Save or cancel the open template before saving the template set."); return; }
    if (!items.length) { setLocalError("Add at least one template."); return; }
    if (items.some((item) => !item.name.trim())) { setLocalError("Each template must have a name."); return; }

    setLocalError(null); setMessage(null);
    await run(async () => {
      let target: BoqTemplatePackage;
      const requestedName = name.trim() || "Project BOQ Template Set";
      if (!activePackage) {
        target = await createBoqTemplatePackage(projectId, { name: requestedName, description: "Project-specific BOQ templates", category: "custom" });
      } else if (activePackage.is_builtin) {
        target = await duplicateBoqTemplatePackage(projectId, activePackage.id, requestedName === activePackage.name ? `${requestedName} - Custom` : requestedName);
      } else {
        target = await updateBoqTemplatePackage(projectId, activePackage.id, { name: requestedName, description: activePackage.description || "Project-specific BOQ templates" });
      }

      const existing = [...target.items];
      const usedIds = new Set<string>();
      for (let index = 0; index < items.length; index += 1) {
        const draft = normalizeItem(items[index], index);
        const match = existing.find((candidate) => candidate.id === draft.id)
          || existing.find((candidate) => !usedIds.has(candidate.id) && candidate.element_type === draft.element_type && candidate.name === draft.name)
          || existing.find((candidate) => !usedIds.has(candidate.id) && candidate.element_type === draft.element_type);
        const payload = toPayload(draft, index);
        if (match) {
          const updated = await updateBoqTemplateItem(projectId, target.id, match.id, payload);
          usedIds.add(updated.id);
        } else {
          const created = await createBoqTemplateItem(projectId, target.id, payload);
          usedIds.add(created.id);
        }
      }
      for (const extra of existing) if (!usedIds.has(extra.id)) await deleteBoqTemplateItem(projectId, target.id, extra.id);
      await selectBoqTemplate(projectId, target.id);
      const refreshed = await query.refetch();
      const saved = refreshed.data?.packages.find((item) => item.id === target.id) || target;
      loadPackageIntoForm(saved);
      setMessage("BOQ templates saved and assigned to this project.");
    }).catch(() => undefined);
  }

  const error = localError || jobError || (query.error instanceof Error ? query.error.message : null);

  return (
    <BoqShell projectId={projectId}>
      <header className="flex min-h-[72px] items-center justify-between gap-4 border-b border-slate-200 bg-white px-6 shadow-sm">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Project Templates</p>
          <h1 className="mt-1 text-lg font-semibold">BOQ Templates</h1>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Link href={appRoutes.workspaceBoq(projectId)}><Button type="button" variant="secondary">Back to BOQ</Button></Link>
          <Button type="button" onClick={() => void saveTemplateSet()} disabled={saving || query.isLoading}>{saving ? "Saving..." : "Save Templates"}</Button>
        </div>
      </header>

      <section className="min-h-[700px] bg-slate-100 p-5">
        {query.isLoading ? <div className="flex min-h-[420px] items-center justify-center"><LoadingState label="Loading BOQ templates" /></div> : (
          <div className="mx-auto flex max-w-[1400px] flex-col gap-5">
            {error ? <ErrorMessage message={error} /> : null}
            {message ? <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">{message}</div> : null}

            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-5">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Template set</p>
                  <input value={name} onChange={(event) => setName(event.target.value)} className="mt-2 h-11 w-full min-w-[280px] rounded-lg border border-slate-200 bg-white px-3 text-lg font-semibold outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100 sm:min-w-[420px]" />
                  {activePackage?.is_builtin ? <p className="mt-2 text-xs text-slate-500">Saving creates an editable project copy of this built-in set.</p> : null}
                </div>
                <div className="grid grid-cols-3 gap-3 text-center">
                  <SummaryBox label="Templates" value={String(items.length)} />
                  <SummaryBox label="Active" value={String(activeItems.length)} />
                  <SummaryBox label="Conditional" value={String(conditionalRuleCount)} />
                </div>
              </div>

              <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-base font-semibold">Template List</h2>
                <Button type="button" onClick={openNewItem}>Add Template</Button>
              </div>

              <div className="mt-4 overflow-hidden rounded-xl border border-slate-200">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                    <tr><th className="px-4 py-3">Template</th><th className="px-4 py-3">Type</th><th className="px-4 py-3">Unit</th><th className="px-4 py-3">Mode</th><th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Action</th></tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 bg-white">
                    {items.map((item, index) => (
                      <tr key={`${item.id || item.name}-${index}`}>
                        <td className="px-4 py-4 font-semibold">{item.name}</td>
                        <td className="px-4 py-4 text-slate-600">{formatElementType(item.element_type)}</td>
                        <td className="px-4 py-4 text-slate-600">{item.unit || "Item"}</td>
                        <td className="px-4 py-4"><ModeBadge mode={item.template_mode || "standard"} /></td>
                        <td className="px-4 py-4"><button type="button" onClick={() => toggleItemStatus(index)} className={item.is_active === false ? "rounded-full bg-slate-200 px-2 py-1 text-xs font-semibold text-slate-600" : "rounded-full bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700"}>{item.is_active === false ? "Inactive" : "Active"}</button></td>
                        <td className="px-4 py-4"><div className="flex justify-end gap-2"><Button type="button" variant="secondary" onClick={() => openEditItem(index)}>Edit</Button><Button type="button" variant="secondary" onClick={() => removeItem(index)}>Remove</Button></div></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {itemDraft ? (
              <TemplateEditor
                itemDraft={itemDraft} editingIndex={editingIndex} itemPreview={itemPreview}
                onCancel={closeItemForm} onSave={saveItemDraft} onDraftChange={updateItemDraft}
                onDraftElementTypeChange={updateItemDraftElementType} onDraftBoqSectionChange={updateItemDraftBoqSection}
                onDraftModeChange={updateItemDraftMode}
              />
            ) : null}
          </div>
        )}
      </section>
    </BoqShell>
  );
}

function TemplateEditor({ itemDraft, editingIndex, itemPreview, onCancel, onSave, onDraftChange, onDraftElementTypeChange, onDraftBoqSectionChange, onDraftModeChange }: {
  itemDraft: ItemDraft; editingIndex: number | null; itemPreview: string; onCancel: () => void; onSave: () => void;
  onDraftChange: (patch: Partial<ItemDraft>) => void; onDraftElementTypeChange: (type: ElementType) => void;
  onDraftBoqSectionChange: (sectionKey: string) => void; onDraftModeChange: (mode: BoqTemplateMode) => void;
}) {
  const boqSectionKey = getBoqSectionKey(itemDraft); const mode = itemDraft.template_mode || "standard";
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-5">
        <div><p className="text-xs font-semibold uppercase tracking-wide text-blue-700">{editingIndex === null ? "Add Template" : "Edit Template"}</p><h2 className="mt-1 text-xl font-semibold">{itemDraft.name || "BOQ Template"}</h2></div>
        <div className="flex gap-2"><Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button><Button type="button" onClick={onSave}>Save Template</Button></div>
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-4">
        <Field label="Template Name"><input value={itemDraft.name} onChange={(event) => onDraftChange({ name: event.target.value })} className="h-11 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100" /></Field>
        <Field label="Type"><select value={itemDraft.element_type} onChange={(event) => onDraftElementTypeChange(event.target.value as ElementType)} className="h-11 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100">{elementTypeOptions.map((type) => <option key={type} value={type}>{formatElementType(type)}</option>)}</select></Field>
        <Field label="Unit"><input value={itemDraft.unit} onChange={(event) => onDraftChange({ unit: event.target.value })} className="h-11 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100" /></Field>
        <Field label="Section"><select value={boqSectionKey} onChange={(event) => onDraftBoqSectionChange(event.target.value)} className="h-11 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100">{boqSectionOptions.map((section) => <option key={section.key} value={section.key}>{section.label}</option>)}</select></Field>
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2"><ModeButton active={mode === "standard"} title="Normal Template" onClick={() => onDraftModeChange("standard")} /><ModeButton active={mode === "conditional"} title="Conditional Template" onClick={() => onDraftModeChange("conditional")} /></div>
      {mode === "standard" ? (
        <div className="mt-5 space-y-5">
          <Field label="Description Template"><textarea value={itemDraft.description_template} onChange={(event) => onDraftChange({ description_template: event.target.value })} rows={5} className="w-full rounded-lg border border-slate-200 bg-white px-4 py-3 font-mono text-xs leading-6 outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100" /></Field>
          <FormulaBuilder value={itemDraft.formula} onChange={(formula) => onDraftChange({ formula })} />
        </div>
      ) : <div className="mt-5"><ConditionalRuleBuilder value={normalizeItemRules(itemDraft)} onChange={(conditional_rules) => onDraftChange({ conditional_rules })} /></div>}
      <div className="mt-5 grid gap-5 md:grid-cols-[1fr_220px]">
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Preview</p><p className="mt-2 text-sm leading-6 text-slate-700">{itemPreview}</p></div>
        <label className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3"><span className="text-sm font-semibold text-slate-800">Active</span><input type="checkbox" checked={itemDraft.is_active !== false} onChange={(event) => onDraftChange({ is_active: event.target.checked })} className="h-5 w-5 rounded border-slate-300" /></label>
      </div>
    </section>
  );
}

function SummaryBox({ label, value }: { label: string; value: string }) { return <div className="min-w-[96px] rounded-xl border border-slate-200 bg-slate-50 px-4 py-3"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p><p className="mt-1 text-lg font-semibold text-slate-950">{value}</p></div>; }
function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="block"><span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span><div className="mt-2">{children}</div></label>; }
function ModeButton({ active, title, onClick }: { active: boolean; title: string; onClick: () => void }) { return <button type="button" onClick={onClick} className={active ? "rounded-xl border border-blue-600 bg-blue-50 px-4 py-3 text-left text-sm font-semibold text-blue-700" : "rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-sm font-semibold text-slate-700 hover:bg-slate-50"}>{title}</button>; }
function ModeBadge({ mode }: { mode: BoqTemplateMode }) { return <span className={`rounded-full px-2 py-1 text-xs font-semibold ${mode === "conditional" ? "bg-blue-50 text-blue-700" : "bg-slate-100 text-slate-700"}`}>{mode === "conditional" ? "Conditional" : "Normal"}</span>; }

function createItemForType(elementType: ElementType = "manual", name?: string): ItemDraft {
  const defaults = elementDefaults[elementType];
  return { name: name || defaults.name, element_type: elementType, section_code: defaults.section_code, section_name: defaults.section_name, unit: defaults.unit, description_template: defaults.description_template, keywords: [...defaults.keywords], template_mode: "standard", conditional_rules: defaultConditionalRulesForType(elementType), formula: { ...defaults.formula, variables: [...defaults.formula.variables] }, sort_order: 0, is_active: true };
}
function cloneItem(item: ItemDraft): ItemDraft { return { ...item, keywords: [...(item.keywords || [])], formula: normalizeFormula(item.formula), conditional_rules: cloneRules(item.conditional_rules) }; }
function cloneItems(items: ItemDraft[]): ItemDraft[] { return items.map(cloneItem); }
function toDraft(item: BoqTemplateItem): ItemDraft { return normalizeItem({ ...item, conditional_rules: normalizeItemRules(item), formula: normalizeFormula(item.formula) }, item.sort_order); }
function normalizeItem(item: ItemDraft, index: number): ItemDraft {
  const defaults = elementDefaults[item.element_type] || elementDefaults.manual;
  return { ...item, name: safeText(item.name) || `BOQ Template ${index + 1}`, section_name: safeText(item.section_name) || defaults.section_name, section_code: item.section_code || defaults.section_code, description_template: safeText(item.description_template) || defaults.description_template, unit: safeText(item.unit) || defaults.unit, keywords: item.keywords || [], sort_order: index, is_active: item.is_active !== false, template_mode: item.template_mode || "standard", formula: normalizeFormula(item.formula), conditional_rules: item.template_mode === "conditional" ? normalizeItemRules(item) : item.conditional_rules };
}
function toPayload(item: ItemDraft, index: number): Omit<BoqTemplateItem, "id" | "template_id"> { const normalized = normalizeItem(item, index); return { name: normalized.name, element_type: normalized.element_type, section_code: normalized.section_code, section_name: normalized.section_name, unit: normalized.unit, description_template: normalized.description_template, keywords: normalized.keywords, template_mode: normalized.template_mode, conditional_rules: normalized.template_mode === "conditional" ? normalizeItemRules(normalized) : [], formula: normalizeFormula(normalized.formula), sort_order: index, is_active: normalized.is_active }; }
function defaultConditionalRulesForType(elementType: ElementType): BoqConditionalRules { const defaults = elementDefaults[elementType]; return { branches: [
  { id: "if-primary", branch_type: "if", conditions: [{ variable: elementType === "door" || elementType === "window" ? "Width" : "Thickness", operator: ">", value: "0", value_type: "number" }], output: { description_template: defaults.description_template, unit: defaults.unit, amount_formula: normalizeFormula(defaults.formula) } },
  { id: "else-default", branch_type: "else", conditions: [], output: { description_template: defaults.description_template, unit: defaults.unit, amount_formula: normalizeFormula(defaults.formula) } },
] }; }
function normalizeItemRules(item: Pick<ItemDraft, "conditional_rules" | "description_template" | "unit" | "formula" | "element_type">): BoqConditionalRules {
  const rules = item.conditional_rules;
  if (rules && !Array.isArray(rules) && Array.isArray(rules.branches)) return normalizeRules(rules);
  if (Array.isArray(rules) && rules.length) {
    const branches: BoqConditionalBranch[] = rules.map((rule: BoqConditionalRule, index) => ({ id: `legacy-${index}`, branch_type: index === 0 ? "if" : "elseif", conditions: [{ variable: rule.field || "Width", operator: rule.operator === "not_equals" ? "!=" : "=", value: rule.operator === "exists" ? "" : rule.value || "", value_type: "string" }], output: { description_template: rule.description_template || `${rule.prefix || ""}${item.description_template}${rule.suffix || ""}`, unit: item.unit, amount_formula: normalizeFormula(item.formula) } }));
    branches.push({ id: "legacy-else", branch_type: "else", conditions: [], output: { description_template: item.description_template, unit: item.unit, amount_formula: normalizeFormula(item.formula) } });
    return normalizeRules({ branches });
  }
  return normalizeRules(defaultConditionalRulesForType(item.element_type));
}
function cloneRules(value: ItemDraft["conditional_rules"]): ItemDraft["conditional_rules"] { if (Array.isArray(value)) return value.map((item) => ({ ...item })); if (value && Array.isArray(value.branches)) return { branches: value.branches.map((branch) => ({ ...branch, conditions: branch.conditions.map((condition) => ({ ...condition })), output: { ...branch.output, amount_formula: normalizeFormula(branch.output.amount_formula) } })) }; return value; }
function renderPreview(item: ItemDraft): string { const template = item.template_mode === "conditional" ? normalizeItemRules(item).branches[0]?.output.description_template || item.description_template : item.description_template; return template.replaceAll("[MATERIAL]", "specified material").replaceAll("[WIDTH]", "900").replaceAll("[HEIGHT]", "2100").replaceAll("[LENGTH]", "10").replaceAll("[THICKNESS]", "215").replaceAll("[FRAME_MATERIAL]", "hardwood").replaceAll("[GLASS_TYPE]", "4 mm clear glass").replaceAll("[TYPE_CODE]", item.element_type === "window" ? "W1" : item.element_type === "door" ? "D1" : "T1").replaceAll("[QUANTITY]", "1").replaceAll("[ROOM_NAME]", "Living Room").replaceAll("[FLOOR_FINISH]", "ceramic tile").replaceAll("[FINISH]", "selected finish").replaceAll("[SIDE_1_FINISH]", "plaster and paint").replaceAll("[SIDE_2_FINISH]", "plaster and paint").replaceAll("[DESCRIPTION]", "General construction item").replaceAll("[UNIT]", item.unit || "Item"); }
function formatElementType(value: string): string { return value.replaceAll("_", " ").split(" ").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" "); }
function getBoqSectionKey(item: Pick<ItemDraft, "section_code" | "section_name">): string { return boqSectionOptions.find((section) => section.section_code === item.section_code && section.section_name === item.section_name)?.key || boqSectionOptions.find((section) => section.section_code === item.section_code)?.key || "general"; }
function safeText(value: unknown): string { return typeof value === "string" ? value.trim() : ""; }
