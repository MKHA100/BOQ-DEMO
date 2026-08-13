"use client";

import Link from "next/link";
import type { SVGProps } from "react";
import { PlatformShell } from "@/features/platform/components/PlatformShell";
import { appRoutes } from "@/shared/constants/appRoutes";

const sources = [
  { title: "PDF Takeoff", icon: PdfIcon, href: appRoutes.pdfGeneration, recommended: true },
  { title: "External File", icon: UploadIcon },
  { title: "ACC Login", icon: CloudIcon },
  { title: "CostX Import", icon: ImportIcon },
  { title: "Revit Import", icon: BuildingIcon },
  { title: "Saved Takeoffs", icon: FolderIcon },
];

export function BoqGenerationPage() {
  return (
    <PlatformShell title="Select BOQ Source" eyebrow="BOQ Generation" activeNavHref={appRoutes.boqGeneration}>
      <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm sm:p-10">
        <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
          {sources.map((source) => {
            const Icon = source.icon;
            const classes = source.recommended
              ? "group relative flex min-h-[270px] flex-col items-center justify-center gap-6 rounded-2xl border-2 border-blue-500 bg-blue-50/30 p-8 text-center shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
              : "relative flex min-h-[270px] flex-col items-center justify-center gap-6 rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm";
            const content = (
              <>
                {source.recommended ? <span className="absolute left-5 top-5 rounded-full bg-blue-600 px-3 py-1 text-xs font-semibold text-white">Recommended</span> : null}
                <span className="flex h-28 w-28 items-center justify-center"><Icon className="h-24 w-24" /></span>
                <span className="text-lg font-semibold text-slate-950">{source.title}</span>
              </>
            );
            return source.href ? <Link key={source.title} href={source.href} className={classes}>{content}</Link> : <div key={source.title} className={`${classes} opacity-70`}>{content}</div>;
          })}
        </div>
      </div>
    </PlatformShell>
  );
}

function Sheet({ children, ...props }: SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 96 96" fill="none" {...props}><path d="M24 8h32l16 16v56a4 4 0 0 1-4 4H24a4 4 0 0 1-4-4V12a4 4 0 0 1 4-4Z" fill="#EFF4FC" stroke="#C9D7EE" strokeWidth={2}/><path d="M56 8v16h16" stroke="#C9D7EE" strokeWidth={2}/>{children}</svg>;
}
function PdfIcon(props: SVGProps<SVGSVGElement>) { return <Sheet {...props}><rect x="25" y="44" width="38" height="23" rx="3" fill="#E0322B"/><text x="44" y="60" textAnchor="middle" fontSize="13" fontWeight="700" fill="white">PDF</text></Sheet>; }
function UploadIcon(props: SVGProps<SVGSVGElement>) { return <Sheet {...props}><circle cx="48" cy="56" r="16" fill="#13A883"/><path d="M48 64V48m0 0-6 6m6-6 6 6" stroke="white" strokeWidth="3" strokeLinecap="round"/></Sheet>; }
function CloudIcon(props: SVGProps<SVGSVGElement>) { return <svg viewBox="0 0 96 96" fill="none" {...props}><path d="M27 70a15 15 0 0 1-1-29 22 22 0 0 1 42 8 11 11 0 0 1-3 21H27Z" fill="#E4EEFC" stroke="#B9CFEF" strokeWidth="2"/><rect x="40" y="48" width="20" height="28" rx="2" fill="#2D6CDF"/></svg>; }
function ImportIcon(props: SVGProps<SVGSVGElement>) { return <svg viewBox="0 0 96 96" fill="none" {...props}><path d="M22 30 46 18l28 12-28 12-24-12Z" fill="#E6FBF6" stroke="#B7E8DA" strokeWidth="2"/><path d="M30 52l16 8 16-8M30 66l16 8 16-8" stroke="#13A883" strokeWidth="5" strokeLinecap="round"/></svg>; }
function BuildingIcon(props: SVGProps<SVGSVGElement>) { return <svg viewBox="0 0 96 96" fill="none" {...props}><rect x="34" y="25" width="28" height="50" rx="2" fill="#2D6CDF"/><rect x="18" y="45" width="16" height="30" fill="#5C8EE8"/><rect x="62" y="38" width="16" height="37" fill="#5C8EE8"/><path d="M20 76h58" stroke="#CFE0F4" strokeWidth="8"/></svg>; }
function FolderIcon(props: SVGProps<SVGSVGElement>) { return <svg viewBox="0 0 96 96" fill="none" {...props}><path d="M16 38a4 4 0 0 1 4-4h24l7 7h25a4 4 0 0 1 4 4v28a4 4 0 0 1-4 4H20a4 4 0 0 1-4-4V42a4 4 0 0 1 4-4Z" fill="#F6C453" stroke="#E0A82E" strokeWidth="2"/><circle cx="61" cy="59" r="12" fill="white" stroke="#13A883" strokeWidth="2"/></svg>; }
