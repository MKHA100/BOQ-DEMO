"use client";

import { PlatformShell } from "@/features/platform/components/PlatformShell";
import { Button } from "@/shared/components/Button";
import { appRoutes } from "@/shared/constants/appRoutes";

export default function WorkspaceError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <PlatformShell title="Project" eyebrow="PDF Generation" activeNavHref={appRoutes.pdfGeneration}>
      <section className="rounded-[28px] border border-slate-200 bg-white p-10 text-center shadow-sm">
        <h2 className="text-xl font-semibold text-slate-950">This workspace could not be opened</h2>
        <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-slate-500">
          Your saved project data is unchanged. Try opening the workspace again.
        </p>
        <div className="mt-6">
          <Button onClick={reset}>Try Again</Button>
        </div>
      </section>
    </PlatformShell>
  );
}
