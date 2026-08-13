"use client";

import { useEffect } from "react";

export function useRoomKeyboardShortcuts({
  enabled,
  onDelete,
  onUndo,
  onRedo,
  onSave,
  onCancel,
}: {
  enabled: boolean;
  onDelete: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  useEffect(() => {
    if (!enabled) return;
    function keydown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target?.matches("input, textarea, select")) return;
      if (event.key === "Delete" || event.key === "Backspace") { event.preventDefault(); onDelete(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") { event.preventDefault(); event.shiftKey ? onRedo() : onUndo(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") { event.preventDefault(); onRedo(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") { event.preventDefault(); onSave(); }
      if (event.key === "Escape") { event.preventDefault(); onCancel(); }
    }
    window.addEventListener("keydown", keydown);
    return () => window.removeEventListener("keydown", keydown);
  }, [enabled, onCancel, onDelete, onRedo, onSave, onUndo]);
}
