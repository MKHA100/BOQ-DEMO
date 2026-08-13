"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { createProject } from "@/features/projects/services/projectService";
import { Button } from "@/shared/components/Button";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import { appRoutes } from "@/shared/constants/appRoutes";

export function ProjectCreateForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [projectNumber, setProjectNumber] = useState("");
  const [clientName, setClientName] = useState("");
  const [location, setLocation] = useState("");
  const [description, setDescription] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanName = name.trim();
    if (!cleanName) {
      setError("Project name is required.");
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const project = await createProject({
        name: cleanName,
        project_number: projectNumber.trim() || null,
        client_name: clientName.trim() || null,
        location: location.trim() || null,
        description: description.trim() || null,
      });
      router.push(appRoutes.workspace(project.project_id));
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Project could not be created.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="max-w-3xl rounded-[28px] border border-slate-200 bg-white p-7 shadow-sm sm:p-8">
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Project name" value={name} onChange={setName} required autoFocus maxLength={120} />
        <Field label="Project number" value={projectNumber} onChange={setProjectNumber} maxLength={80} />
        <Field label="Client" value={clientName} onChange={setClientName} maxLength={120} />
        <Field label="Location" value={location} onChange={setLocation} maxLength={160} />
      </div>
      <label className="mt-5 block">
        <span className="text-sm font-semibold text-slate-700">Description</span>
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          maxLength={1000}
          rows={4}
          className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
        />
      </label>
      {error ? <div className="mt-4"><ErrorMessage message={error} /></div> : null}
      <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Button type="button" variant="secondary" className="rounded-xl px-6" onClick={() => router.push(appRoutes.projects)} disabled={isSaving}>
          Cancel
        </Button>
        <Button disabled={isSaving || !name.trim()} className="rounded-xl px-6">
          {isSaving ? "Creating" : "Create project"}
        </Button>
      </div>
    </form>
  );
}

function Field({
  label,
  value,
  onChange,
  required = false,
  autoFocus = false,
  maxLength,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  autoFocus?: boolean;
  maxLength?: number;
}) {
  return (
    <label className="block">
      <span className="text-sm font-semibold text-slate-700">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required={required}
        autoFocus={autoFocus}
        maxLength={maxLength}
        className="mt-3 h-12 w-full rounded-xl border border-slate-200 bg-white px-4 text-sm outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
      />
    </label>
  );
}
