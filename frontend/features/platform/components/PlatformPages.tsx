"use client";

import { FormEvent, useEffect, useState } from "react";
import { Button } from "@/shared/components/Button";
import { ErrorMessage } from "@/shared/components/ErrorMessage";
import { LoadingState } from "@/shared/components/LoadingState";
import { appRoutes } from "@/shared/constants/appRoutes";
import { PlatformShell } from "./PlatformShell";
import { ActionCard, Card, DataTable, StatCard } from "./PlatformCards";
import {
  createOrganization,
  createSubscriptionPlan,
  createSuperAdmin,
  getAdminOverview,
  getAccountSettings,
  getOrganizationOverview,
  getOrganizationSettings,
  getProfile,
  getUsage,
  inviteOrganizationMember,
  listAuditLogs,
  listBillingHistory,
  listNotifications,
  listOrganizationMembers,
  listOrganizationRoles,
  listOrganizations,
  listSubscriptionPlans,
  listSuperAdmins,
  requestPasswordReset,
  updateAccountSettings,
  updateOrganizationSettings,
  updateProfile,
  type PlatformRecord,
} from "../services/platformService";

function useRecords(loader: () => Promise<PlatformRecord[]>) {
  const [rows, setRows] = useState<PlatformRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    setIsLoading(true);
    setError(null);
    try {
      setRows(await loader());
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Data could not be loaded.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  return { rows, isLoading, error, reload };
}

function useRecord(loader: () => Promise<PlatformRecord>) {
  const [record, setRecord] = useState<PlatformRecord | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      setError(null);
      try {
        setRecord(await loader());
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : "Data could not be loaded.");
      } finally {
        setIsLoading(false);
      }
    }
    void load();
  }, []);

  return { record, isLoading, error };
}

export function AdminDashboardPage() {
  const { record, isLoading, error } = useRecord(getAdminOverview);
  return (
    <PlatformShell title="Super Admin" eyebrow="Administration">
      {isLoading ? <LoadingState label="Loading overview" /> : null}
      {error ? <ErrorMessage message={error} /> : null}
      <div className="grid gap-5 md:grid-cols-4">
        <StatCard label="Organizations" value={String(record?.organizations ?? 0)} />
        <StatCard label="Users" value={String(record?.users ?? 0)} />
        <StatCard label="Subscriptions" value={String(record?.active_subscriptions ?? 0)} />
        <StatCard label="Projects" value={String(record?.projects ?? 0)} />
      </div>
      <div className="mt-6 grid gap-5 md:grid-cols-3">
        <ActionCard title="Organizations" description="Create, update and suspend client organizations." href={appRoutes.adminOrganizations} action="Manage" />
        <ActionCard title="Super Admins" description="Create and review platform administrator accounts." href={appRoutes.adminSuperAdmins} action="Manage" />
        <ActionCard title="Subscriptions" description="Manage product plans and subscription controls." href={appRoutes.adminSubscriptions} action="Manage" />
      </div>
    </PlatformShell>
  );
}

export function OrganizationManagementPage() {
  const { rows, isLoading, error, reload } = useRecords(listOrganizations);
  const [name, setName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [planSlug, setPlanSlug] = useState("starter");
  const [message, setMessage] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage(null);
    await createOrganization({ name, admin_email: adminEmail || null, plan_slug: planSlug });
    setName("");
    setAdminEmail("");
    setMessage("Organization created.");
    await reload();
  }

  return (
    <PlatformShell title="Organizations" eyebrow="Administration">
      <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <Card>
          <h2 className="text-xl font-semibold text-slate-950">Create organization</h2>
          <form className="mt-5 space-y-4" onSubmit={submit}>
            <Input label="Organization name" value={name} onChange={setName} required />
            <Input label="Admin email" value={adminEmail} onChange={setAdminEmail} type="email" />
            <Select label="Plan" value={planSlug} onChange={setPlanSlug} options={["starter", "professional", "enterprise"]} />
            <Button className="w-full rounded-xl">Create</Button>
            {message ? <p className="text-sm font-medium text-emerald-700">{message}</p> : null}
          </form>
        </Card>
        <Card>
          {isLoading ? <LoadingState label="Loading organizations" /> : null}
          {error ? <ErrorMessage message={error} /> : null}
          <DataTable columns={["name", "slug", "status", "user_limit", "project_limit", "created_at"]} rows={rows} />
        </Card>
      </div>
    </PlatformShell>
  );
}

export function SuperAdminsPage() {
  const { rows, isLoading, error, reload } = useRecords(listSuperAdmins);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    await createSuperAdmin({ email, full_name: fullName || null, password });
    setEmail("");
    setFullName("");
    setPassword("");
    await reload();
  }

  return (
    <PlatformShell title="Super Admins" eyebrow="Administration">
      <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <Card>
          <h2 className="text-xl font-semibold text-slate-950">Create super admin</h2>
          <form className="mt-5 space-y-4" onSubmit={submit}>
            <Input label="Full name" value={fullName} onChange={setFullName} />
            <Input label="Email" value={email} onChange={setEmail} type="email" required />
            <Input label="Password" value={password} onChange={setPassword} type="password" required />
            <Button className="w-full rounded-xl">Create</Button>
          </form>
        </Card>
        <Card>
          {isLoading ? <LoadingState label="Loading admins" /> : null}
          {error ? <ErrorMessage message={error} /> : null}
          <DataTable columns={["email", "full_name", "role", "status", "created_at"]} rows={rows} />
        </Card>
      </div>
    </PlatformShell>
  );
}

export function SubscriptionPlansPage() {
  const { rows, isLoading, error, reload } = useRecords(listSubscriptionPlans);
  const [form, setForm] = useState({ name: "", slug: "", price_monthly: "0", user_limit: "5", project_limit: "10", storage_limit_mb: "1024" });

  async function submit(event: FormEvent) {
    event.preventDefault();
    await createSubscriptionPlan({ ...form, price_monthly: Number(form.price_monthly), user_limit: Number(form.user_limit), project_limit: Number(form.project_limit), storage_limit_mb: Number(form.storage_limit_mb), export_limit_monthly: 100, ai_credit_limit_monthly: 1000, currency: "USD", features: [] });
    setForm({ name: "", slug: "", price_monthly: "0", user_limit: "5", project_limit: "10", storage_limit_mb: "1024" });
    await reload();
  }

  return (
    <PlatformShell title="Subscription Plans" eyebrow="Administration">
      <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <Card>
          <h2 className="text-xl font-semibold text-slate-950">Create plan</h2>
          <form className="mt-5 space-y-4" onSubmit={submit}>
            <Input label="Name" value={form.name} onChange={(value) => setForm({ ...form, name: value })} required />
            <Input label="Slug" value={form.slug} onChange={(value) => setForm({ ...form, slug: value })} required />
            <Input label="Monthly price" value={form.price_monthly} onChange={(value) => setForm({ ...form, price_monthly: value })} />
            <Input label="User limit" value={form.user_limit} onChange={(value) => setForm({ ...form, user_limit: value })} />
            <Input label="Project limit" value={form.project_limit} onChange={(value) => setForm({ ...form, project_limit: value })} />
            <Button className="w-full rounded-xl">Create</Button>
          </form>
        </Card>
        <Card>
          {isLoading ? <LoadingState label="Loading plans" /> : null}
          {error ? <ErrorMessage message={error} /> : null}
          <DataTable columns={["name", "slug", "price_monthly", "currency", "user_limit", "project_limit", "status"]} rows={rows} />
        </Card>
      </div>
    </PlatformShell>
  );
}

export function OrganizationDashboardPage() {
  const { record, isLoading, error } = useRecord(getOrganizationOverview);
  const organization = (record?.organization as PlatformRecord | undefined) ?? {};
  const subscription = (record?.subscription as PlatformRecord | undefined) ?? {};
  return (
    <PlatformShell title="Organization" eyebrow="Management" activeNavHref={appRoutes.organization}>
      {isLoading ? <LoadingState label="Loading organization" /> : null}
      {error ? <ErrorMessage message={error} /> : null}
      {!isLoading && !record?.organization ? (
        <Card><p className="text-sm text-slate-600">No organization workspace is linked to this account.</p></Card>
      ) : null}
      {record?.organization ? (
        <>
          <Card className="mb-6">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Workspace</p>
            <h2 className="mt-2 text-xl font-semibold text-slate-950">{String(organization.name ?? "Organization")}</h2>
            <p className="mt-1 text-sm capitalize text-slate-500">{String(organization.status ?? "active")}</p>
          </Card>
          <div className="grid gap-5 md:grid-cols-3">
            <StatCard label="Members" value={String(record?.members ?? 0)} />
            <StatCard label="Projects" value={String(record?.projects ?? 0)} />
            <StatCard label="Plan" value={String(subscription.plan_name ?? "Starter")} />
          </div>
          <div className="mt-6 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            <ActionCard title="Members" description="Invite users and manage workspace access." href={appRoutes.organizationMembers} action="Manage" />
            <ActionCard title="Roles" description="Review the available roles and permissions." href={appRoutes.organizationRoles} action="View" />
            <ActionCard title="Billing" description="Review the current plan and billing history." href={appRoutes.organizationBilling} action="Open" />
            <ActionCard title="Usage" description="Review project and storage usage." href={appRoutes.usage} action="View" />
            <ActionCard title="Settings" description="Manage organization preferences." href={appRoutes.organizationSettings} action="Open" />
          </div>
        </>
      ) : null}
    </PlatformShell>
  );
}

export function MembersPage() {
  const { rows, isLoading, error, reload } = useRecords(listOrganizationMembers);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");

  async function submit(event: FormEvent) {
    event.preventDefault();
    await inviteOrganizationMember({ email, role });
    setEmail("");
    setRole("member");
    await reload();
  }

  return (
    <PlatformShell title="Members" eyebrow="Organization">
      <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <Card>
          <h2 className="text-xl font-semibold text-slate-950">Invite member</h2>
          <form className="mt-5 space-y-4" onSubmit={submit}>
            <Input label="Email" value={email} onChange={setEmail} type="email" required />
            <Select label="Role" value={role} onChange={setRole} options={["organization_admin", "project_manager", "quantity_surveyor", "reviewer", "viewer"]} />
            <Button className="w-full rounded-xl">Send invitation</Button>
          </form>
        </Card>
        <Card>
          {isLoading ? <LoadingState label="Loading members" /> : null}
          {error ? <ErrorMessage message={error} /> : null}
          <DataTable columns={["email", "full_name", "role", "status", "created_at"]} rows={rows} />
        </Card>
      </div>
    </PlatformShell>
  );
}

export function RolesPage() {
  const { rows, isLoading, error } = useRecords(listOrganizationRoles);
  return (
    <PlatformShell title="Roles and Permissions" eyebrow="Organization">
      <Card>
        {isLoading ? <LoadingState label="Loading roles" /> : null}
        {error ? <ErrorMessage message={error} /> : null}
        <DataTable columns={["name", "slug", "permissions"]} rows={rows} />
      </Card>
    </PlatformShell>
  );
}



export function BillingPage({ title = "Billing" }: { title?: string }) {
  const { rows, isLoading, error } = useRecords(listBillingHistory);
  return (
    <PlatformShell title={title} eyebrow="Billing">
      <Card>
        {isLoading ? <LoadingState label="Loading billing history" /> : null}
        {error ? <ErrorMessage message={error} /> : null}
        <DataTable columns={["provider", "amount", "currency", "status", "description", "created_at"]} rows={rows} />
      </Card>
    </PlatformShell>
  );
}

export function AuditLogPage() {
  const { rows, isLoading, error } = useRecords(listAuditLogs);
  return (
    <PlatformShell title="Audit Logs" eyebrow="Administration">
      <Card>
        {isLoading ? <LoadingState label="Loading audit logs" /> : null}
        {error ? <ErrorMessage message={error} /> : null}
        <DataTable columns={["action", "entity_type", "entity_id", "user_id", "created_at"]} rows={rows} />
      </Card>
    </PlatformShell>
  );
}

export function UsagePage() {
  const { record, isLoading, error } = useRecord(getUsage);
  const usage = (record?.usage as PlatformRecord | undefined) ?? {};
  const limits = (record?.limits as PlatformRecord | undefined) ?? {};
  return (
    <PlatformShell title="Usage Limits" eyebrow="Organization">
      {isLoading ? <LoadingState label="Loading usage" /> : null}
      {error ? <ErrorMessage message={error} /> : null}
      <div className="grid gap-5 md:grid-cols-2">
        <StatCard label="Projects" value={`${usage.projects_created ?? 0} / ${limits.projects ?? 0}`} />
        <StatCard label="Storage" value={`${usage.storage_used_mb ?? 0} MB`} helper={`${limits.storage_mb ?? 0} MB limit`} />
      </div>
    </PlatformShell>
  );
}

export function NotificationsPage() {
  const { rows, isLoading, error } = useRecords(listNotifications);
  return (
    <PlatformShell title="Email Notifications" eyebrow="Communication">
      <Card>
        {isLoading ? <LoadingState label="Loading notifications" /> : null}
        {error ? <ErrorMessage message={error} /> : null}
        <DataTable columns={["channel", "recipient", "subject", "status", "created_at"]} rows={rows} />
      </Card>
    </PlatformShell>
  );
}

export function ProfilePage() {
  const { record, isLoading, error } = useRecord(getProfile);
  const profile = (record?.profile as PlatformRecord | undefined) ?? {};
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [timezone, setTimezone] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setFullName(String(profile.full_name ?? ""));
    setPhone(String(profile.phone ?? ""));
    setJobTitle(String(profile.job_title ?? ""));
    setTimezone(String(profile.timezone ?? ""));
  }, [record]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    await updateProfile({ full_name: fullName, phone, job_title: jobTitle, timezone });
    setMessage("Profile updated.");
  }

  return (
    <PlatformShell title="Profile" eyebrow="Account">
      <Card className="max-w-2xl">
        {isLoading ? <LoadingState label="Loading profile" /> : null}
        {error ? <ErrorMessage message={error} /> : null}
        <form className="space-y-4" onSubmit={submit}>
          <Input label="Full name" value={fullName} onChange={setFullName} />
          <Input label="Phone" value={phone} onChange={setPhone} />
          <Input label="Job title" value={jobTitle} onChange={setJobTitle} />
          <Input label="Timezone" value={timezone} onChange={setTimezone} />
          <Button className="rounded-xl">Save profile</Button>
          {message ? <p className="text-sm font-medium text-emerald-700">{message}</p> : null}
        </form>
      </Card>
    </PlatformShell>
  );
}

export function SettingsPage({ scope = "account" }: { scope?: "account" | "organization" | "admin" }) {
  const [emailUpdates, setEmailUpdates] = useState("enabled");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const loader = scope === "organization" ? getOrganizationSettings : getAccountSettings;
    loader()
      .then((settings) => {
        if (mounted) setEmailUpdates(String(settings.email_updates ?? "enabled"));
      })
      .catch((nextError) => {
        if (mounted) setError(nextError instanceof Error ? nextError.message : "Settings could not be loaded.");
      })
      .finally(() => {
        if (mounted) setIsLoading(false);
      });
    return () => { mounted = false; };
  }, [scope]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    setMessage(null);
    try {
      if (scope === "organization") {
        await updateOrganizationSettings({ email_updates: emailUpdates });
      } else {
        await updateAccountSettings({ email_updates: emailUpdates });
      }
      setMessage("Settings saved.");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Settings could not be saved.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <PlatformShell title="Settings" eyebrow={scope === "admin" ? "Administration" : scope === "organization" ? "Organization" : "Account"}>
      <Card className="max-w-2xl">
        {isLoading ? <LoadingState label="Loading settings" /> : null}
        {error ? <div className="mb-4"><ErrorMessage message={error} /></div> : null}
        {!isLoading ? (
          <form className="space-y-4" onSubmit={submit}>
            <Select label="Email notifications" value={emailUpdates} onChange={setEmailUpdates} options={["enabled", "disabled"]} />
            <Button className="rounded-xl" disabled={isSaving}>{isSaving ? "Saving" : "Save settings"}</Button>
            {message ? <p className="text-sm font-medium text-emerald-700">{message}</p> : null}
          </form>
        ) : null}
      </Card>
    </PlatformShell>
  );
}


export function AccountSecurityPage() {
  return (
    <PlatformShell title="Security" eyebrow="Account">
      <Card className="max-w-2xl">
        <h2 className="text-xl font-semibold text-slate-950">Password and access</h2>
        <p className="mt-3 text-sm leading-6 text-slate-500">Password reset is available from the login screen. Two-factor authentication can be connected in the next security phase.</p>
      </Card>
    </PlatformShell>
  );
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await requestPasswordReset(email);
      setMessage("If the account exists, a reset notification has been queued.");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Reset request failed.");
    }
  }
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#eef3f8] px-6 py-10">
      <Card className="w-full max-w-md">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Reset password</h1>
        <form className="mt-6 space-y-4" onSubmit={submit}>
          <Input label="Email" value={email} onChange={setEmail} type="email" required />
          <Button className="w-full rounded-xl">Send reset link</Button>
          {message ? <p className="text-sm font-medium text-emerald-700">{message}</p> : null}
          {error ? <ErrorMessage message={error} /> : null}
        </form>
      </Card>
    </main>
  );
}

function Input({ label, value, onChange, type = "text", required = false }: { label: string; value: string; onChange: (value: string) => void; type?: string; required?: boolean }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <input type={type} value={value} required={required} onChange={(event) => onChange(event.target.value)} className="mt-2 h-12 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100" />
    </label>
  );
}

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: string[] }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} className="mt-2 h-12 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100">
        {options.map((option) => <option key={option} value={option}>{option.replaceAll("_", " ")}</option>)}
      </select>
    </label>
  );
}