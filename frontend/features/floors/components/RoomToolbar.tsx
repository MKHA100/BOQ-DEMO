"use client";

import { Button } from "@/shared/components/Button";
import type { FloorEditorTool } from "../store/useFloorEditorStore";
import { FloorToolPanel } from "./FloorToolPanel";
import { AdvancedRoomMenu } from "./AdvancedRoomMenu";

export function RoomToolbar({
  processing,
  hasRooms,
  hasSelection,
  autoFixing,
  tool,
  editing,
  canUndo,
  canRedo,
  onTool,
  onAnalyze,
  onRecalculate,
  onConfirmAll,
  onAutoFix,
  onSimplify,
  onRectangle,
  onStraighten,
  onSnap,
  onUndo,
  onRedo,
  onSave,
  onCancel,
}: {
  processing: boolean;
  hasRooms: boolean;
  hasSelection: boolean;
  autoFixing: boolean;
  tool: FloorEditorTool;
  editing: boolean;
  canUndo: boolean;
  canRedo: boolean;
  onTool: (tool: FloorEditorTool) => void;
  onAnalyze: () => void;
  onRecalculate: () => void;
  onConfirmAll: () => void;
  onAutoFix: () => void;
  onSimplify: () => void;
  onRectangle: () => void;
  onStraighten: () => void;
  onSnap: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="flex min-h-14 flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-white px-4 py-2">
      <FloorToolPanel
        tool={tool}
        editing={editing}
        canUndo={canUndo}
        canRedo={canRedo}
        hasSelection={hasSelection}
        autoFixing={autoFixing}
        onTool={onTool}
        onAutoFix={onAutoFix}
        onSimplify={onSimplify}
        onRectangle={onRectangle}
        onStraighten={onStraighten}
        onSnap={onSnap}
        onUndo={onUndo}
        onRedo={onRedo}
        onSave={onSave}
        onCancel={onCancel}
      />
      {!editing ? (
        <div className="flex flex-wrap items-center gap-2">
          {hasSelection ? (
            <AdvancedRoomMenu
              onRectangle={onRectangle}
              onSnap={onSnap}
              onSimplify={onSimplify}
              onSplit={() => onTool("split")}
              onCutout={() => onTool("cutout")}
              onFinishZone={() => onTool("zone")}
            />
          ) : null}
          <Button variant="secondary" disabled={processing} onClick={onAnalyze}>{processing ? "Analyzing…" : "Analyze rooms"}</Button>
          {hasRooms ? <Button variant="secondary" disabled={processing} onClick={onRecalculate}>Recalculate</Button> : null}
          {hasRooms ? <Button disabled={processing} onClick={onConfirmAll}>Approve floor</Button> : null}
        </div>
      ) : null}
    </div>
  );
}
