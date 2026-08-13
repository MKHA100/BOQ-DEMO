"use client";

import { createPortal } from "react-dom";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

export function AdvancedRoomMenu({
  disabled,
  onRectangle,
  onSnap,
  onSimplify,
  onSplit,
  onCutout,
  onFinishZone,
}: {
  disabled?: boolean;
  onRectangle: () => void;
  onSnap: () => void;
  onSimplify: () => void;
  onSplit: () => void;
  onCutout: () => void;
  onFinishZone: () => void;
}) {
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });

  useEffect(() => setMounted(true), []);

  useLayoutEffect(() => {
    if (!open || !buttonRef.current) return;
    const update = () => {
      const rect = buttonRef.current?.getBoundingClientRect();
      if (!rect) return;
      const width = 224;
      const left = Math.max(12, Math.min(window.innerWidth - width - 12, rect.right - width));
      setPosition({ top: rect.bottom + 8, left });
    };
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      const target = event.target as Node;
      if (buttonRef.current?.contains(target) || menuRef.current?.contains(target)) return;
      setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  const run = (action: () => void) => {
    setOpen(false);
    action();
  };

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        disabled={disabled}
        aria-haspopup="menu"
        aria-expanded={open}
        className="inline-flex items-center justify-center rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-900 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
        onClick={() => setOpen((value) => !value)}
      >
        Advanced <span className="ml-1 text-xs">▾</span>
      </button>
      {mounted && open
        ? createPortal(
          <div
            ref={menuRef}
            role="menu"
            className="fixed z-[1000] w-56 rounded-xl border border-slate-200 bg-white p-2 shadow-2xl"
            style={{ top: position.top, left: position.left }}
          >
            <p className="px-3 pb-2 pt-1 text-[11px] font-semibold uppercase tracking-[.12em] text-slate-400">Geometry</p>
            <MenuItem label="Make rectangle" onClick={() => run(onRectangle)} />
            <MenuItem label="Snap to wall faces" onClick={() => run(onSnap)} />
            <MenuItem label="Remove extra points" onClick={() => run(onSimplify)} />
            <div className="my-2 border-t border-slate-100" />
            <p className="px-3 pb-2 pt-1 text-[11px] font-semibold uppercase tracking-[.12em] text-slate-400">Advanced editing</p>
            <MenuItem label="Split by line" onClick={() => run(onSplit)} />
            <MenuItem label="Cutout / void" onClick={() => run(onCutout)} />
            <MenuItem label="Create finish zone" onClick={() => run(onFinishZone)} />
          </div>,
          document.body,
        )
        : null}
    </>
  );
}

function MenuItem({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      role="menuitem"
      className="w-full rounded-lg px-3 py-2 text-left text-sm font-medium text-slate-700 hover:bg-slate-50 focus:bg-slate-50 focus:outline-none"
      onClick={onClick}
    >
      {label}
    </button>
  );
}
