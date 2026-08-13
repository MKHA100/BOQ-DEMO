import type { ReactNode } from "react";

export type WorkflowTableColumn<TRow> = {
  key: string;
  header: string;
  render: (row: TRow) => ReactNode;
};

export function WorkflowTable<TRow extends { id: string }>({
  rows,
  columns,
}: {
  rows: TRow[];
  columns: Array<WorkflowTableColumn<TRow>>;
}) {
  return (
    <div className="overflow-auto rounded-2xl border border-slate-200 bg-white">
      <table className="min-w-full border-collapse text-left text-sm">
        <thead className="sticky top-0 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
          <tr>{columns.map((column) => <th key={column.key} className="px-4 py-3">{column.header}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr key={row.id}>{columns.map((column) => <td key={column.key} className="px-4 py-3 text-slate-700">{column.render(row)}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
