import type { FloorSummary } from "../types";

export function FloorSelector({
  floors,
  value,
  onChange,
  disabled = false,
}: {
  floors: FloorSummary[];
  value: string | null;
  onChange: (floorId: string) => void;
  disabled?: boolean;
}) {
  return (
    <label className="flex items-center gap-3">
      <span className="text-sm font-semibold text-slate-600">Floor</span>
      <select
        aria-label="Floor"
        className="h-10 min-w-44 rounded-xl border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100 disabled:bg-slate-50"
        value={value ?? ""}
        disabled={disabled || floors.length === 0}
        onChange={(event) => onChange(event.target.value)}
      >
        {floors.length === 0 ? <option value="">No floors</option> : null}
        {floors.map((floor) => (
          <option key={floor.id} value={floor.id}>
            {floor.name}
          </option>
        ))}
      </select>
    </label>
  );
}
