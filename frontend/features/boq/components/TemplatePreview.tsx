export function TemplatePreview({ description }: { description: string }) {
  return <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Generated preview</p><p className="mt-2 text-sm leading-6 text-emerald-950">{description || "Save the template item to generate a preview."}</p></div>;
}
