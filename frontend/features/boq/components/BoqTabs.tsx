"use client";

import Link from "next/link";
import { appRoutes } from "@/shared/constants/appRoutes";

export type BoqTabKey = "report" | "setup" | "templates" | "exports";

export function BoqTabs({ projectId, active }: { projectId: string; active: BoqTabKey }) {
  const tabs = [
    ["report", "BOQ Report", appRoutes.workspaceBoq(projectId)],
    ["setup", "Document Setup", appRoutes.workspaceBoqSetup(projectId)],
    ["templates", "Templates", appRoutes.workspaceBoqTemplates(projectId)],
    ["exports", "Exports", appRoutes.workspaceBoqExports(projectId)],
  ] as const;
  return (
    <nav className="flex flex-wrap gap-1 border-b border-slate-200 bg-white px-5 pt-4">
      {tabs.map(([key, label, href]) => (
        <Link key={key} href={href} className={`rounded-t-lg border-b-2 px-4 py-3 text-sm font-semibold transition ${active === key ? "border-blue-600 bg-blue-50/60 text-blue-700" : "border-transparent text-slate-500 hover:text-slate-900"}`}>
          {label}
        </Link>
      ))}
    </nav>
  );
}
