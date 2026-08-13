"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { getProject, updateProject } from "@/features/projects/services/projectService";
import { PlatformShell } from "@/features/platform/components/PlatformShell";
import { Button } from "@/shared/components/Button";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import { LoadingState } from "@/shared/components/LoadingState";
import { appRoutes } from "@/shared/constants/appRoutes";
import type { ProjectResponse, ProjectStatus } from "@/shared/types/apiTypes";

export function ProjectOverviewPage({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<ProjectResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    getProject(projectId)
      .then((nextProject) => {
        if (mounted) setProject(nextProject);
      })
      .catch((nextError) => {
        if (mounted) setError(nextError instanceof Error ? nextError.message : "Project could not be loaded.");
      });
    return () => {
      mounted = false;
    };
  }, [projectId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!project) return;
    setIsSaving(true);
    setError(null);
    setSavedMessage(null);
    try {
      const saved = await updateProject(project.id, {
        name: project.name,
        project_number: project.project_number,
        client_name: project.client_name,
        location: project.location,
        description: project.description,
        status: project.status,
      });
      setProject(saved);
      setSavedMessage("Project details saved.");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Project could not be updated.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <PlatformShell title={project?.name || "Project"} eyebrow="Project Library" activeNavHref={appRoutes.projects}>
      {!project && !error ? <LoadingState label="Loading project" /> : null}
      {error ? <div className="mb-5"><ErrorMessage message={error} /></div> : null}
      {project ? (
        <div className="grid gap-7 xl:grid-cols-[minmax(0,1fr)_330px]">
          <form onSubmit={submit} className="rounded-[28px] border border-slate-200 bg-white p-7 shadow-sm sm:p-8">
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Project name" value={project.name} onChange={(value) => setProject({ ...project, name: value })} required />
              <Field label="Project number" value={project.project_number || ""} onChange={(value) => setProject({ ...project, project_number: value || null })} />
              <Field label="Client" value={project.client_name || ""} onChange={(value) => setProject({ ...project, client_name: value || null })} />
              <Field label="Location" value={project.location || ""} onChange={(value) => setProject({ ...project, location: value || null })} />
              <label className="block sm:col-span-2">
                <span className="text-sm font-semibold text-slate-700">Status</span>
                <select
                  value={project.status}
                  onChange={(event) => setProject({ ...project, status: event.target.value as ProjectStatus })}
                  className="mt-3 h-12 w-full rounded-xl border border-slate-200 bg-white px-4 text-sm outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
                >
                  <option value="active">Active</option>
                  <option value="on_hold">On hold</option>
                  <option value="completed">Completed</option>
                  <option value="archived">Archived</option>
                </select>
              </label>
            </div>
            <label className="mt-5 block">
              <span className="text-sm font-semibold text-slate-700">Description</span>
              <textarea
                value={project.description || ""}
                onChange={(event) => setProject({ ...project, description: event.target.value || null })}
                rows={5}
                maxLength={1000}
                className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
              />
            </label>
            <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
              <Link href={appRoutes.projects} className="text-sm font-semibold text-slate-600 hover:text-blue-700">Back to projects</Link>
              <div className="flex items-center gap-3">
                {savedMessage ? <span className="text-sm font-medium text-emerald-700">{savedMessage}</span> : null}
                <Button disabled={isSaving || !project.name.trim()} className="rounded-xl px-6">
                  {isSaving ? "Saving" : "Save details"}
                </Button>
              </div>
            </div>
          </form>

          <aside className="space-y-5">
            <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">PDF Generation</p>
              <h2 className="mt-3 text-lg font-semibold text-slate-950">Project workspace</h2>
              <p className="mt-2 text-sm leading-6 text-slate-500">Open the current AutoBOQ workflow foundation for this project.</p>
              <Link
                href={appRoutes.workflowUpload(project.id)}
                className="mt-5 inline-flex h-11 w-full items-center justify-center rounded-xl bg-slate-950 px-5 text-sm font-semibold text-white transition hover:bg-blue-700"
              >
                Open PDF Generation
              </Link>
            </section>

            <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Ownership</p>
              <dl className="mt-4 space-y-3 text-sm">
                <Detail label="Organization" value={project.organization_name || "Workspace"} />
                <Detail label="Created" value={formatDate(project.created_at)} />
                <Detail label="Updated" value={formatDate(project.updated_at)} />
              </dl>
            </section>
          </aside>
        </div>
      ) : null}
    </PlatformShell>
  );
}

function Field({ label, value, onChange, required = false }: { label: string; value: string; onChange: (value: string) => void; required?: boolean }) {
  return (
    <label className="block">
      <span className="text-sm font-semibold text-slate-700">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required={required}
        className="mt-3 h-12 w-full rounded-xl border border-slate-200 bg-white px-4 text-sm outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
      />
    </label>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-900">{value}</dd>
    </div>
  );
}

function formatDate(value: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "2-digit" }).format(new Date(value));
  } catch {
    return value;
  }
}
