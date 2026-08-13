"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode, type SVGProps } from "react";
import { AuthGuard } from "@/features/auth/components/AuthGuard";
import { SignOutButton } from "@/features/auth/components/SignOutButton";
import {
  getCachedPlatformContext,
  getPlatformContext,
  type PlatformContext,
} from "@/features/platform/services/platformService";
import { appRoutes } from "@/shared/constants/appRoutes";

type NavItem = {
  title: string;
  href: string;
};

const workspaceNav: NavItem[] = [
  { title: "Dashboard", href: appRoutes.dashboard },
  { title: "Automated BOQ", href: appRoutes.boqGeneration },
  { title: "PDF Generation", href: appRoutes.pdfGeneration },
  { title: "Project Library", href: appRoutes.projects },
];

const organizationNav: NavItem[] = [
  { title: "Overview", href: appRoutes.organization },
  { title: "Members", href: appRoutes.organizationMembers },
  { title: "Roles", href: appRoutes.organizationRoles },
  { title: "Billing", href: appRoutes.organizationBilling },
  { title: "Usage", href: appRoutes.usage },
  { title: "Settings", href: appRoutes.organizationSettings },
];

const accountNav: NavItem[] = [
  { title: "Profile", href: appRoutes.accountProfile },
  { title: "Account Settings", href: appRoutes.accountSettings },
  { title: "Security", href: appRoutes.accountSecurity },
  { title: "Notifications", href: appRoutes.notifications },
];

const adminNav: NavItem[] = [
  { title: "Overview", href: appRoutes.admin },
  { title: "Organizations", href: appRoutes.adminOrganizations },
  { title: "Super Admins", href: appRoutes.adminSuperAdmins },
  { title: "Subscriptions", href: appRoutes.adminSubscriptions },
  { title: "Billing", href: appRoutes.adminBilling },
  { title: "Audit Logs", href: appRoutes.adminAuditLogs },
  { title: "Settings", href: appRoutes.adminSettings },
];

const DESKTOP_NAV_KEY = "autoboq:navigation:collapsed";

export function PlatformShell({
  title,
  eyebrow,
  children,
  activeNavHref,
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  activeNavHref?: string;
}) {
  const [context, setContext] = useState<PlatformContext | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [desktopCollapsed, setDesktopCollapsed] = useState(false);

  useEffect(() => {
    let mounted = true;
    const cached = getCachedPlatformContext();
    if (cached) setContext(cached);

    getPlatformContext()
      .then((nextContext) => {
        if (mounted) setContext(nextContext);
      })
      .catch(() => undefined);
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    const saved = window.localStorage.getItem(DESKTOP_NAV_KEY);
    setDesktopCollapsed(saved === "true");
  }, []);

  const showOrganization = Boolean(context?.organization);
  const showAdmin = Boolean(context?.is_super_admin);
  const organizationName = useMemo(() => context?.organization?.name || "Workspace", [context]);

  function toggleDesktopNavigation() {
    setDesktopCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem(DESKTOP_NAV_KEY, String(next));
      return next;
    });
  }

  const navigation = (
    <>
      <div className="flex items-center gap-3 px-1">
        <HexLogoIcon className="h-10 w-10" />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-950">AutoBOQ</p>
          <p className="truncate text-xs text-slate-500">{organizationName}</p>
        </div>
      </div>
      <NavigationGroup title="Workspace" items={workspaceNav} activeHref={activeNavHref} onNavigate={() => setMobileOpen(false)} />
      {showOrganization ? (
        <NavigationGroup title="Organization" items={organizationNav} activeHref={activeNavHref} onNavigate={() => setMobileOpen(false)} />
      ) : null}
      <NavigationGroup title="Account" items={accountNav} activeHref={activeNavHref} onNavigate={() => setMobileOpen(false)} />
      {showAdmin ? (
        <NavigationGroup title="Administration" items={adminNav} activeHref={activeNavHref} onNavigate={() => setMobileOpen(false)} />
      ) : null}
    </>
  );

  return (
    <AuthGuard>
      <main className="autoboq-ui min-h-screen bg-[#eef3f8] text-slate-950">
        <div className="flex min-h-screen w-full">
          <aside
            aria-hidden={desktopCollapsed}
            className={`hidden shrink-0 overflow-hidden bg-white transition-[width,border-color] duration-200 xl:block ${
              desktopCollapsed ? "w-0 border-r-0 border-transparent" : "w-[280px] border-r border-slate-200"
            }`}
          >
            <div className={`h-full w-[280px] overflow-y-auto px-5 py-6 transition-opacity duration-150 ${desktopCollapsed ? "pointer-events-none opacity-0" : "opacity-100"}`}>
              {navigation}
            </div>
          </aside>

          {mobileOpen ? (
            <div className="fixed inset-0 z-50 xl:hidden">
              <button
                type="button"
                aria-label="Close navigation"
                className="absolute inset-0 bg-slate-950/35"
                onClick={() => setMobileOpen(false)}
              />
              <aside className="relative h-full w-[290px] overflow-y-auto border-r border-slate-200 bg-white px-5 py-6 shadow-2xl">
                <div className="flex items-center justify-between">
                  <span className="sr-only">Navigation</span>
                  <button
                    type="button"
                    className="ml-auto rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600"
                    onClick={() => setMobileOpen(false)}
                  >
                    Close
                  </button>
                </div>
                <div className="mt-4">{navigation}</div>
              </aside>
            </div>
          ) : null}

          <section className="flex min-w-0 flex-1 flex-col">
            <header className="flex min-h-[72px] shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-4 py-3 sm:px-6 lg:px-8">
              <div className="flex min-w-0 items-center gap-3">
                <button
                  type="button"
                  aria-label="Open navigation"
                  className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-slate-200 text-slate-600 xl:hidden"
                  onClick={() => setMobileOpen(true)}
                >
                  <MenuIcon className="h-5 w-5" />
                </button>
                <button
                  type="button"
                  aria-label={desktopCollapsed ? "Show navigation" : "Hide navigation"}
                  title={desktopCollapsed ? "Show navigation" : "Hide navigation"}
                  className="hidden h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700 xl:inline-flex"
                  onClick={toggleDesktopNavigation}
                >
                  <SidebarToggleIcon collapsed={desktopCollapsed} className="h-5 w-5" />
                </button>
                <div className="min-w-0">
                  {eyebrow ? <p className="truncate text-xs font-semibold uppercase tracking-[0.22em] text-blue-700">{eyebrow}</p> : null}
                  <h1 className="mt-1 truncate text-xl font-semibold tracking-tight text-slate-950 sm:text-2xl">{title}</h1>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Link
                  href={appRoutes.notifications}
                  className="hidden h-10 items-center rounded-lg border border-slate-200 bg-white px-4 text-sm font-medium text-slate-600 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700 md:inline-flex"
                >
                  Notifications
                </Link>
                <Link
                  href={appRoutes.accountProfile}
                  className="hidden h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 text-sm font-medium text-slate-600 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700 sm:inline-flex"
                >
                  <UserBadgeIcon className="h-4 w-4" />
                  Profile
                </Link>
                <SignOutButton className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-600 transition hover:border-red-200 hover:bg-red-50 hover:text-red-600 sm:px-4" />
              </div>
            </header>
            <div className="flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</div>
          </section>
        </div>
      </main>
    </AuthGuard>
  );
}

function NavigationGroup({
  title,
  items,
  activeHref,
  onNavigate,
}: {
  title: string;
  items: NavItem[];
  activeHref?: string;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const effectiveActiveHref = activeHref ?? pathname;

  return (
    <nav className="mt-8">
      <p className="px-4 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{title}</p>
      <div className="mt-3 space-y-1">
        {items.map((item) => {
          const active =
            effectiveActiveHref === item.href ||
            (item.href !== appRoutes.dashboard && effectiveActiveHref.startsWith(`${item.href}/`));
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={
                active
                  ? "flex items-center rounded-xl border-l-2 border-blue-600 bg-blue-50 px-4 py-2.5 text-sm font-semibold text-blue-700"
                  : "flex items-center rounded-xl border-l-2 border-transparent px-4 py-2.5 text-sm font-medium text-slate-600 transition hover:bg-slate-50 hover:text-slate-950"
              }
            >
              {item.title}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

function HexLogoIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 40 40" fill="none" {...props}>
      <path d="M20 3 35 11.5v17L20 37 5 28.5v-17L20 3Z" fill="#EAF1FD" stroke="#2D6CDF" strokeWidth={2} strokeLinejoin="round" />
      <circle cx="20" cy="20" r="7" fill="#2D6CDF" />
      <path d="M17 20.2 19.3 22.5 23.5 17.8" stroke="white" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function UserBadgeIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} {...props}>
      <circle cx="12" cy="8.5" r="3.5" />
      <path strokeLinecap="round" d="M5 19.5a7 7 0 0 1 14 0" />
    </svg>
  );
}

function MenuIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" {...props}>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  );
}

function SidebarToggleIcon({ collapsed, ...props }: SVGProps<SVGSVGElement> & { collapsed: boolean }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <rect x="3.5" y="4" width="17" height="16" rx="2.5" />
      <path d="M9 4v16" />
      <path d={collapsed ? "m13 9 3 3-3 3" : "m16 9-3 3 3 3"} />
    </svg>
  );
}
