"use client";

import { Button } from "@/shared/components/Button";
import type { FloorEditorTool } from "../store/useFloorEditorStore";

export function FloorToolPanel({
  tool,
  editing,
  canUndo,
  canRedo,
  hasSelection,
  autoFixing,
  onTool,
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
  tool: FloorEditorTool;
  editing: boolean;
  canUndo: boolean;
  canRedo: boolean;
  hasSelection: boolean;
  autoFixing: boolean;
  onTool: (tool: FloorEditorTool) => void;
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
  if (!editing) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <Button variant={tool === "select" ? "primary" : "secondary"} onClick={() => onTool("select")}>Select</Button>
        <Button variant={tool === "pan" ? "primary" : "secondary"} onClick={() => onTool("pan")}>Hand</Button>
        <Button variant={tool === "draw_room" ? "primary" : "secondary"} onClick={() => onTool("draw_room")}>Add room</Button>
        <Button variant="secondary" disabled={!hasSelection || autoFixing} onClick={onAutoFix}>{autoFixing ? "Auto-fixing…" : "Auto-fix"}</Button>
        <Button variant="secondary" disabled={!hasSelection} onClick={() => onTool("edit_vertex")}>Edit shape</Button>
      </div>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button variant={tool === "edit_vertex" ? "primary" : "secondary"} onClick={() => onTool("edit_vertex")}>Move point</Button>
      <Button variant={tool === "add_vertex" ? "primary" : "secondary"} onClick={() => onTool("add_vertex")}>Add point</Button>
      <Button variant={tool === "delete_vertex" ? "primary" : "secondary"} onClick={() => onTool("delete_vertex")}>Delete point</Button>
      <Button variant={tool === "move_edge" ? "primary" : "secondary"} onClick={() => onTool("move_edge")}>Move edge</Button>
      <Button variant="secondary" onClick={onSnap}>Snap</Button>
      <Button variant="secondary" onClick={onStraighten}>Straighten</Button>
      <Button variant="secondary" onClick={onSimplify}>Simplify</Button>
      <Button variant="secondary" onClick={onRectangle}>Rectangle</Button>
      <Button variant="secondary" disabled={!canUndo} onClick={onUndo}>Undo</Button>
      <Button variant="secondary" disabled={!canRedo} onClick={onRedo}>Redo</Button>
      <Button variant="secondary" onClick={onCancel}>Cancel</Button>
      <Button onClick={onSave}>Save shape</Button>
    </div>
  );
}
