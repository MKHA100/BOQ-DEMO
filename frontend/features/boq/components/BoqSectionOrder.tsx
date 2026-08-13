"use client";

export function BoqSectionOrder({ value, onChange }: { value: string[]; onChange: (value: string[]) => void }) {
  function move(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= value.length) return;
    const next = [...value]; [next[index], next[target]] = [next[target], next[index]]; onChange(next);
  }
  return (
    <div className="space-y-2">
      {value.map((section, index) => (
        <div key={`${section}-${index}`} className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2">
          <span className="text-sm font-semibold text-slate-700">Bill {section}</span>
          <div className="flex gap-1"><button className="rounded border px-2 py-1 text-xs" onClick={() => move(index, -1)} type="button">Up</button><button className="rounded border px-2 py-1 text-xs" onClick={() => move(index, 1)} type="button">Down</button></div>
        </div>
      ))}
    </div>
  );
}
