"use client";

import Link from "next/link";
import { useEffect, useState, type SVGProps } from "react";
import { PlatformShell } from "@/features/platform/components/PlatformShell";
import { getCachedDashboardSummary, getDashboardSummary, type DashboardSummary } from "@/features/platform/services/platformService";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import { appRoutes } from "@/shared/constants/appRoutes";

export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const cached = getCachedDashboardSummary();
    if (cached) setSummary(cached);

    getDashboardSummary().then((value) => { if (active) setSummary(value); }).catch((nextError) => {
      if (active) setError(nextError instanceof Error ? nextError.message : "Dashboard data could not be loaded.");
    });
    return () => { active = false; };
  }, []);

  return (
    <PlatformShell title="Dashboard" eyebrow="Workspace" activeNavHref={appRoutes.dashboard}>
      {error ? <div className="mb-5"><ErrorMessage message={error} /></div> : null}
      <div className="grid gap-7 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-7">
          <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
            <div className="grid gap-5 md:grid-cols-3">
              <DashboardCard title="Automated BOQ" href={appRoutes.boqGeneration} action="Start" icon={BoqIcon} />
              <DashboardCard title="Project Library" href={appRoutes.projects} action="Open" icon={ProjectIcon} />
              <DashboardCard title="PDF Generation" href={appRoutes.pdfGeneration} action="Upload PDF" icon={PdfIcon} />
            </div>
          </section>

          <section className="rounded-[28px] border border-slate-200 bg-white p-7 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold tracking-tight text-slate-950">Recent Projects / Takeoffs</h2>
              <Link href={appRoutes.projects} className="text-sm font-semibold text-blue-700">View all</Link>
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {summary?.recent_projects?.length ? summary.recent_projects.slice(0, 4).map((project) => (
                <Link key={project.id} href={appRoutes.workspace(project.id)} className="rounded-2xl border border-slate-200 bg-white p-5 transition hover:border-blue-200 hover:shadow-sm">
                  <p className="truncate font-semibold text-slate-950">{project.name}</p>
                  <p className="mt-2 truncate text-sm text-slate-500">{[project.project_number, project.client_name].filter(Boolean).join(" · ") || "Construction project"}</p>
                  <span className="mt-4 inline-flex text-xs font-semibold text-blue-700">Open project</span>
                </Link>
              )) : (
                <div className="col-span-full rounded-2xl border border-dashed border-slate-200 p-8 text-center">
                  <p className="text-sm text-slate-500">No projects are available yet.</p>
                  <Link href={appRoutes.pdfGeneration} className="mt-3 inline-flex text-sm font-semibold text-blue-700">Start PDF Generation</Link>
                </div>
              )}
            </div>
          </section>
        </div>

        <div className="space-y-7">
          <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Account Scope</p>
            <div className="mt-4 flex items-center gap-3">
              <ShieldIcon className="h-10 w-10" />
              <div>
                <p className="text-sm font-semibold text-slate-950">{summary?.context.organization?.name || "Organization workspace"}</p>
                <p className="mt-1 text-xs capitalize text-slate-500">{(summary?.context.membership_role || summary?.context.user.role || "member").replaceAll("_", " ")}</p>
              </div>
            </div>
          </section>
          <DashboardCard title="Account Profile" href={appRoutes.accountProfile} action="Open profile" icon={ProfileIcon} compact />
        </div>
      </div>
    </PlatformShell>
  );
}

function DashboardCard({ title, href, action, icon: Icon, compact = false }: { title: string; href: string; action: string; icon: (props: SVGProps<SVGSVGElement>) => JSX.Element; compact?: boolean }) {
  return (
    <Link href={href} className={`${compact ? "min-h-[150px]" : "min-h-[220px]"} group flex flex-col items-center justify-center gap-4 rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm transition hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-md`}>
      <span className={compact ? "h-14 w-14" : "h-24 w-24"}><Icon className="h-full w-full transition group-hover:scale-105" /></span>
      <span className="font-semibold text-slate-950">{title}</span>
      <span className="text-xs font-semibold text-blue-700">{action}</span>
    </Link>
  );
}
function Sheet({ children, ...props }: SVGProps<SVGSVGElement>) { return <svg viewBox="0 0 96 96" fill="none" {...props}><path d="M24 8h32l16 16v56a4 4 0 0 1-4 4H24a4 4 0 0 1-4-4V12a4 4 0 0 1 4-4Z" fill="#EFF4FC" stroke="#C9D7EE" strokeWidth="2"/><path d="M56 8v16h16" stroke="#C9D7EE" strokeWidth="2"/>{children}</svg>; }
function BoqIcon(props: SVGProps<SVGSVGElement>) { return <Sheet {...props}><rect x="28" y="42" width="34" height="30" rx="3" fill="#2D6CDF"/><path d="M34 50h22M34 58h22M34 66h14" stroke="#BFD6FA" strokeWidth="3"/></Sheet>; }
function PdfIcon(props: SVGProps<SVGSVGElement>) { return <Sheet {...props}><rect x="25" y="44" width="38" height="23" rx="3" fill="#E0322B"/><text x="44" y="60" textAnchor="middle" fontSize="13" fontWeight="700" fill="white">PDF</text></Sheet>; }
function ProjectIcon(props: SVGProps<SVGSVGElement>) { return <svg viewBox="0 0 96 96" fill="none" {...props}><path d="M16 38a4 4 0 0 1 4-4h24l7 7h25a4 4 0 0 1 4 4v28a4 4 0 0 1-4 4H20a4 4 0 0 1-4-4V42a4 4 0 0 1 4-4Z" fill="#F6C453" stroke="#E0A82E" strokeWidth="2"/></svg>; }
function ProfileIcon(props: SVGProps<SVGSVGElement>) { return <svg viewBox="0 0 96 96" fill="none" {...props}><circle cx="48" cy="48" r="34" fill="#E4EEFC" stroke="#B9CFEF" strokeWidth="2"/><circle cx="48" cy="40" r="11" fill="#2D6CDF"/><path d="M27 74c2-12 10-19 21-19s19 7 21 19" fill="#2D6CDF"/></svg>; }
function ShieldIcon(props: SVGProps<SVGSVGElement>) { return <svg viewBox="0 0 48 48" fill="none" {...props}><path d="M24 4 40 10v12c0 12-8 18-16 22-8-4-16-10-16-22V10L24 4Z" fill="#EAF1FD" stroke="#2D6CDF" strokeWidth="2"/><path d="m17 24 5 5 9-10" stroke="#2D6CDF" strokeWidth="2.5" strokeLinecap="round"/></svg>; }
