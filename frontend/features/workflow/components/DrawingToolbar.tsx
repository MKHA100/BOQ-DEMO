import type { ReactNode } from "react";

export type DrawingTool = {
  key: string;
  label: string;
  icon?: ReactNode;
};

export function DrawingToolbar({
  tools,
  activeTool,
  onSelect,
}: {
  tools: DrawingTool[];
  activeTool?: string;
  onSelect: (tool: string) => void;
}) {
  return (
    <div className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
      {tools.map((tool) => (
        <button
          key={tool.key}
          type="button"
          title={tool.label}
          aria-pressed={activeTool === tool.key}
          onClick={() => onSelect(tool.key)}
          className={
            activeTool === tool.key
              ? "inline-flex h-9 items-center gap-2 rounded-lg bg-blue-50 px-3 text-sm font-semibold text-blue-700"
              : "inline-flex h-9 items-center gap-2 rounded-lg px-3 text-sm font-medium text-slate-600 hover:bg-slate-50"
          }
        >
          {tool.icon}
          {tool.label}
        </button>
      ))}
    </div>
  );
}
