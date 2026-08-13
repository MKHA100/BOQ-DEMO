"use client";

import Link from "next/link";
import { appRoutes } from "@/shared/constants/appRoutes";

export function ReviewViewTabs({
  projectId,
  active,
}: {
  projectId: string;
  active: "items" | "types";
}) {
  const base =
    "inline-flex h-9 items-center justify-center rounded-lg px-3.5 text-sm font-semibold transition";
  const activeClass = "bg-slate-950 text-white";
  const idleClass = "text-slate-600 hover:bg-slate-100 hover:text-slate-950";

  return (
    <div className="inline-flex rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
      <Link
        href={appRoutes.workflowStep(projectId, "review")}
        className={`${base} ${active === "items" ? activeClass : idleClass}`}
      >
        Detailed review
      </Link>
      <Link
        href={appRoutes.workspaceReviewTypes(projectId)}
        className={`${base} ${active === "types" ? activeClass : idleClass}`}
      >
        Type summary
      </Link>
    </div>
  );
}
