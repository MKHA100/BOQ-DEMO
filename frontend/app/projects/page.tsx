"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { PlatformShell } from "@/features/platform/components/PlatformShell";
import { getCachedProjects, listProjects } from "@/features/projects/services/projectService";
import { Button } from "@/shared/components/Button";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import { appRoutes } from "@/shared/constants/appRoutes";
import type { ProjectListResponse, ProjectStatus } from "@/shared/types/apiTypes";

const PAGE_SIZE = 12;

function formatDate(value: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "2-digit" }).format(new Date(value));
  } catch {
    return value;
  }
}

function statusLabel(status: string): string {
  return status.replaceAll("_", " ");
}

export default function ProjectsPage() {
  const [response, setResponse] = useState<ProjectListResponse>({ projects: [], total: 0, limit: PAGE_SIZE, offset: 0 });
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"" | ProjectStatus>("");
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const canUseDefaultCache = !search && !status && offset === 0;
    const cached = canUseDefaultCache ? getCachedProjects() : null;
    if (cached) {
      setResponse(cached);
      setIsLoading(false);
    } else {
      setIsLoading(true);
    }
    setError(null);
    listProjects({ search, status: status || undefined, limit: PAGE_SIZE, offset })
      .then((nextResponse) => {
        if (mounted) setResponse(nextResponse);
      })
      .catch((nextError) => {
        if (mounted) setError(nextError instanceof Error ? nextError.message : "Projects could not be loaded.");
      })
      .finally(() => {
        if (mounted) setIsLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [offset, search, status]);

  const pageNumber = useMemo(() => Math.floor(response.offset / response.limit) + 1, [response.limit, response.offset]);
  const totalPages = Math.max(1, Math.ceil(response.total / response.limit));

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setOffset(0);
    setSearch(searchInput.trim());
  }

  return (
    <PlatformShell title="Projects" eyebrow="Project Library" activeNavHref={appRoutes.projects}>
      <div className="mb-6 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <form onSubmit={submitSearch} className="flex flex-1 flex-col gap-3 sm:flex-row sm:items-end">
          <label className="block flex-1">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Search</span>
            <input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Project name, number, client or location"
              className="mt-2 h-11 w-full rounded-xl border border-slate-200 bg-white px-4 text-sm outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
            />
          </label>
          <label className="block sm:w-44">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Status</span>
            <select
              value={status}
              onChange={(event) => {
                setOffset(0);
                setStatus(event.target.value as "" | ProjectStatus);
              }}
              className="mt-2 h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
            >
              <option value="">Current projects</option>
              <option value="active">Active</option>
              <option value="on_hold">On hold</option>
              <option value="completed">Completed</option>
              <option value="archived">Archived</option>
            </select>
          </label>
          <Button className="h-11 rounded-xl px-5">Search</Button>
        </form>
        <Link href={appRoutes.createProject}>
          <Button className="h-11 w-full rounded-xl px-5 sm:w-auto">Create Project</Button>
        </Link>
      </div>

      {error ? <div className="mb-5"><ErrorMessage message={error} /></div> : null}

      <div className="mb-4 flex items-center justify-between text-sm text-slate-500">
        <span>{response.total} project{response.total === 1 ? "" : "s"}</span>
        {isLoading ? <span>Updating</span> : null}
      </div>

      {!isLoading && response.projects.length === 0 ? (
        <section className="rounded-[28px] border border-slate-200 bg-white p-10 text-center shadow-sm">
          <h2 className="text-xl font-semibold text-slate-950">No projects found</h2>
          <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-slate-500">
            Adjust the search or create a new project.
          </p>
          <div className="mt-6"><Link href={appRoutes.createProject}><Button>Create Project</Button></Link></div>
        </section>
      ) : null}

      {response.projects.length > 0 ? (
        <section className="grid gap-5 md:grid-cols-2 2xl:grid-cols-3">
          {response.projects.map((project) => (
            <article key={project.id} className="flex min-h-[250px] flex-col rounded-[24px] border border-slate-200 bg-white p-6 shadow-sm transition hover:border-blue-200 hover:shadow-md">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <Link href={appRoutes.workspace(project.id)} className="block truncate text-lg font-semibold text-slate-950 hover:text-blue-700">
                    {project.name}
                  </Link>
                  <p className="mt-1 truncate text-sm text-slate-500">{project.project_number || "No project number"}</p>
                </div>
                <span className="shrink-0 rounded-full bg-blue-50 px-3 py-1 text-xs font-medium capitalize text-blue-700">
                  {statusLabel(project.status)}
                </span>
              </div>

              <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
                <ProjectDetail label="Client" value={project.client_name || "Not set"} />
                <ProjectDetail label="Location" value={project.location || "Not set"} />
                <ProjectDetail label="Organization" value={project.organization_name || "Workspace"} />
                <ProjectDetail label="Updated" value={formatDate(project.updated_at)} />
              </dl>

              <div className="mt-auto flex flex-col gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
                <Link href={appRoutes.workspace(project.id)} className="text-sm font-semibold text-slate-700 hover:text-blue-700">
                  Project details
                </Link>
                <Link
                  href={appRoutes.workflowUpload(project.id)}
                  className="inline-flex h-10 items-center justify-center rounded-xl bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-blue-700"
                >
                  Open PDF Generation
                </Link>
              </div>
            </article>
          ))}
        </section>
      ) : null}

      {response.total > PAGE_SIZE ? (
        <div className="mt-7 flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
          <Button
            type="button"
            variant="secondary"
            disabled={offset === 0 || isLoading}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            Previous
          </Button>
          <span className="text-sm font-medium text-slate-600">Page {pageNumber} of {totalPages}</span>
          <Button
            type="button"
            variant="secondary"
            disabled={offset + PAGE_SIZE >= response.total || isLoading}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Next
          </Button>
        </div>
      ) : null}
    </PlatformShell>
  );
}

function ProjectDetail({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-slate-50 p-3">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-1 truncate font-medium text-slate-900">{value}</dd>
    </div>
  );
}
