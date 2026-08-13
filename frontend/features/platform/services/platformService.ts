import { getCachedJson, requestJson } from "@/shared/services/apiClient";
import type { ProjectListItem } from "@/shared/types/apiTypes";

export type PlatformContext = {
  user: {
    id: string;
    email: string;
    full_name?: string | null;
    role: string;
    status: string;
  };
  organization?: {
    id: string;
    name: string;
    status: string;
    membership_role?: string;
  } | null;
  membership_role?: string;
  permissions: string[];
  is_super_admin: boolean;
};

export type PlatformRecord = Record<string, unknown>;

export type DashboardSummary = {
  context: PlatformContext;
  project_count: number;
  recent_projects: ProjectListItem[];
  member_count: number;
  notification_count: number;
  usage: {
    usage?: {
      projects_created?: number;
      storage_used_mb?: number;
    };
    limits?: {
      projects?: number;
      storage_mb?: number;
    };
  };
};

const CONTEXT_PATH = "/api/v1/platform/me";
const DASHBOARD_PATH = "/api/v1/platform/dashboard-summary";
const REAL_API_BASE_URL = process.env.NEXT_PUBLIC_REAL_API_BASE_URL || "http://localhost:8001";
const REAL_DASHBOARD_URL = `${REAL_API_BASE_URL}${DASHBOARD_PATH}`;

export function getCachedPlatformContext(): PlatformContext | null {
  return getCachedJson<PlatformContext>(CONTEXT_PATH);
}

export function getPlatformContext() {
  return requestJson<PlatformContext>(CONTEXT_PATH);
}

export function getCachedDashboardSummary(): DashboardSummary | null {
  // Dashboard data comes from the real backend. Do not hydrate it with a
  // cached response previously returned by the demo backend.
  return null;
}

export function getDashboardSummary() {
  return requestJson<DashboardSummary>(REAL_DASHBOARD_URL);
}

export function getAdminOverview() {
  return requestJson<PlatformRecord>("/api/v1/platform/admin/overview");
}

export function listOrganizations() {
  return requestJson<PlatformRecord[]>("/api/v1/platform/admin/organizations");
}

export function createOrganization(payload: PlatformRecord) {
  return requestJson<PlatformRecord>("/api/v1/platform/admin/organizations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listSuperAdmins() {
  return requestJson<PlatformRecord[]>("/api/v1/platform/admin/super-admins");
}

export function createSuperAdmin(payload: PlatformRecord) {
  return requestJson<PlatformRecord>("/api/v1/platform/admin/super-admins", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listSubscriptionPlans() {
  return requestJson<PlatformRecord[]>("/api/v1/platform/admin/subscription-plans");
}

export function createSubscriptionPlan(payload: PlatformRecord) {
  return requestJson<PlatformRecord>("/api/v1/platform/admin/subscription-plans", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getOrganizationOverview() {
  return requestJson<PlatformRecord>("/api/v1/platform/organization/overview");
}

export function listOrganizationMembers() {
  return requestJson<PlatformRecord[]>("/api/v1/platform/organization/members");
}

export function inviteOrganizationMember(payload: PlatformRecord) {
  return requestJson<PlatformRecord>("/api/v1/platform/organization/invitations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listOrganizationRoles() {
  return requestJson<PlatformRecord[]>("/api/v1/platform/organization/roles");
}

export function getOrganizationSettings() {
  return requestJson<PlatformRecord>("/api/v1/platform/organization/settings");
}

export function updateOrganizationSettings(settings: PlatformRecord) {
  return requestJson<PlatformRecord>("/api/v1/platform/organization/settings", {
    method: "PATCH",
    body: JSON.stringify({ settings }),
  });
}

export function listAuditLogs() {
  return requestJson<PlatformRecord[]>("/api/v1/platform/audit-logs");
}

export function listBillingHistory() {
  return requestJson<PlatformRecord[]>("/api/v1/platform/billing-history");
}

export function getUsage() {
  return requestJson<PlatformRecord>("/api/v1/platform/usage");
}

export function getProfile() {
  return requestJson<PlatformRecord>("/api/v1/platform/account/profile");
}

export function updateProfile(payload: PlatformRecord) {
  return requestJson<PlatformRecord>("/api/v1/platform/account/profile", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function getAccountSettings() {
  return requestJson<PlatformRecord>("/api/v1/platform/account/settings");
}

export function updateAccountSettings(settings: PlatformRecord) {
  return requestJson<PlatformRecord>("/api/v1/platform/account/settings", {
    method: "PATCH",
    body: JSON.stringify({ settings }),
  });
}

export function requestPasswordReset(email: string) {
  return requestJson<PlatformRecord>("/api/v1/platform/password-reset/request", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function listNotifications() {
  return requestJson<PlatformRecord[]>("/api/v1/platform/notifications");
}
