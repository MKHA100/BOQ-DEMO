"use client";

import { useEffect, useState } from "react";
import { Button } from "@/shared/components/Button";
import type { BoqTemplatePackage } from "../types";

export function BoqTemplateCreateDialog({
  open,
  templates,
  defaultTemplateId,
  saving,
  onClose,
  onCreate,
}: {
  open: boolean;
  templates: BoqTemplatePackage[];
  defaultTemplateId: string;
  saving: boolean;
  onClose: () => void;
  onCreate: (name: string, baseTemplateId: string | null) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [baseTemplateId, setBaseTemplateId] = useState(defaultTemplateId || "blank");

  useEffect(() => {
    if (!open) return;
    setName("");
    setBaseTemplateId(defaultTemplateId || templates[0]?.id || "blank");
  }, [defaultTemplateId, open, templates]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/40 p-4" role="dialog" aria-modal="true" aria-label="Add BOQ template">
      <button type="button" className="absolute inset-0 cursor-default" aria-label="Close" onClick={onClose} />
      <section className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Add template</h2>
            <p className="mt-1 text-sm text-slate-500">Create a copy to customize, or start blank.</p>
          </div>
          <button type="button" className="text-2xl leading-none text-slate-400 hover:text-slate-700" onClick={onClose} aria-label="Close">×</button>
        </div>

        <div className="mt-5 space-y-4">
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Template name</span>
            <input className="input mt-2 w-full" autoFocus value={name} onChange={(event) => setName(event.target.value)} placeholder="Company BOQ template" />
          </label>
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Start from</span>
            <select className="input mt-2 w-full" value={baseTemplateId} onChange={(event) => setBaseTemplateId(event.target.value)}>
              {templates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}
              <option value="blank">Blank template</option>
            </select>
          </label>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="secondary" disabled={saving} onClick={onClose}>Cancel</Button>
          <Button disabled={saving || !name.trim()} onClick={() => void onCreate(name.trim(), baseTemplateId === "blank" ? null : baseTemplateId)}>
            {saving ? "Creating…" : "Create and edit"}
          </Button>
        </div>
      </section>
    </div>
  );
}
