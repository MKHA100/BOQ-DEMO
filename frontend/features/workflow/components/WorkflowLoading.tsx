import { PlatformShell } from "@/features/platform/components/PlatformShell";
import { appRoutes } from "@/shared/constants/appRoutes";

export function WorkflowLoading() {
  return (
    <PlatformShell title="Project" eyebrow="PDF Generation" activeNavHref={appRoutes.pdfGeneration}>
      <div className="overflow-hidden rounded-[28px] border border-slate-200 bg-[#f7f9fc] shadow-sm">
        <div className="flex gap-3 overflow-hidden border-b border-slate-200 bg-white px-6 py-4">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="h-8 w-24 shrink-0 animate-pulse rounded-lg bg-slate-100" />
          ))}
        </div>
        <div className="flex min-h-20 items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
          <div className="h-6 w-40 animate-pulse rounded bg-slate-100" />
          <div className="h-10 w-44 animate-pulse rounded-xl bg-slate-100" />
        </div>
        <div className="p-5 lg:p-6">
          <div className="min-h-[420px] rounded-[24px] border border-slate-200 bg-white">
            <div className="h-1 w-1/3 animate-pulse rounded-t-[24px] bg-blue-500" />
          </div>
        </div>
      </div>
    </PlatformShell>
  );
}
