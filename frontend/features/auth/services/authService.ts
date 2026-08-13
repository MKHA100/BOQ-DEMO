import { requestJson } from "@/shared/services/apiClient";

export type AuthUser = {
  id: string | null;
  email: string;
  created_at?: string;
  full_name?: string | null;
  role: string;
  status: string;
  organization_id?: string | null;
  organization_name?: string | null;
};

type AuthResponse = {
  access_token: string;
  token_type: string;
  user: AuthUser;
};

export const AUTH_TOKEN_KEY = "construction_plan_extractor_token";
export const AUTH_USER_KEY = "construction_plan_extractor_user";

export function isLocalDevelopmentSession(): boolean {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname;
  return ["localhost", "127.0.0.1", "0.0.0.0", "::1"].includes(host)
    // Cloudflare Quick Tunnels are used only to share this unauthenticated demo.
    // The real hosted application still requires a normal authenticated session.
    || host.endsWith(".trycloudflare.com");
}

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(AUTH_TOKEN_KEY);
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const value = window.localStorage.getItem(AUTH_USER_KEY);
  if (!value) return null;
  try {
    return JSON.parse(value) as AuthUser;
  } catch {
    window.localStorage.removeItem(AUTH_USER_KEY);
    return null;
  }
}

function persistAuth(response: AuthResponse): AuthResponse {
  window.localStorage.setItem(AUTH_TOKEN_KEY, response.access_token);
  window.localStorage.setItem(AUTH_USER_KEY, JSON.stringify(response.user));
  return response;
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const response = await requestJson<AuthResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  return persistAuth(response);
}

export async function register(email: string, password: string): Promise<AuthResponse> {
  const response = await requestJson<AuthResponse>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  return persistAuth(response);
}

export async function loadCurrentUser(): Promise<AuthUser> {
  return requestJson<AuthUser>("/api/v1/auth/me");
}

export async function logout(): Promise<void> {
  try {
    await requestJson<{ status: string }>("/api/v1/auth/logout", { method: "POST" });
  } catch {
    // local/dev sessions may not have a server token to invalidate
  } finally {
    window.localStorage.removeItem(AUTH_TOKEN_KEY);
    window.localStorage.removeItem(AUTH_USER_KEY);
  }
}
