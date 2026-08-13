import type { BoqPlaceholder } from "../types";

export function PlaceholderPicker({ placeholders, onPick }: { placeholders: BoqPlaceholder[]; onPick: (token: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {placeholders.map((item) => <button key={item.key} type="button" title={`${item.label}: ${item.example}`} onClick={() => onPick(`[${item.key}]`)} className="rounded-md border border-blue-200 bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-700">{item.key}</button>)}
    </div>
  );
}
