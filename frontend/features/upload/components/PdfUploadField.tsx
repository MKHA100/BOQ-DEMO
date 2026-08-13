"use client";

import { useRef, useState, type ChangeEvent, type DragEvent } from "react";

export function PdfUploadField({
  disabled,
  onSelect,
}: {
  disabled?: boolean;
  onSelect: (file: File) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function selectFromInput(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) onSelect(file);
    event.target.value = "";
  }

  function dropFile(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) onSelect(file);
  }

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(event) => {
        if (!disabled && (event.key === "Enter" || event.key === " ")) inputRef.current?.click();
      }}
      onDragEnter={(event) => {
        event.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={() => setDragging(false)}
      onDrop={dropFile}
      className={`flex min-h-56 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 text-center transition ${
        dragging ? "border-blue-500 bg-blue-50" : "border-slate-300 bg-slate-50 hover:border-slate-400 hover:bg-slate-100"
      } ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
    >
      <input ref={inputRef} type="file" accept="application/pdf,.pdf" className="hidden" onChange={selectFromInput} />
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-slate-200 bg-white text-xl font-semibold text-slate-600 shadow-sm">
        PDF
      </div>
      <p className="text-base font-semibold text-slate-950">Choose a construction PDF</p>
      <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">Select a file or drag it into this area.</p>
    </div>
  );
}
