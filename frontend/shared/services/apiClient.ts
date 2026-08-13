const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const AUTH_TOKEN_KEY = "construction_plan_extractor_token";
const CACHE_PREFIX = "cpe_cache:";

export class ApiRequestError extends Error {
  status: number;
  rawMessage?: string;

  constructor(status: number, message: string, rawMessage?: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.rawMessage = rawMessage;
  }
}

export function apiUrl(path: string): string {
  if (path.startsWith("http")) return path;
  return `${API_BASE_URL}${path}`;
}

export function authHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = window.localStorage.getItem(AUTH_TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function isLocalBrowser(): boolean {
  if (typeof window === "undefined") return false;
  return ["localhost", "127.0.0.1", "0.0.0.0", "::1"].includes(window.location.hostname);
}

export function localDevHeader(): Record<string, string> {
  return isLocalBrowser() ? { "X-Local-Dev-Bypass": "1" } : {};
}


export function apiRequestHeaders(): Record<string, string> {
  return { ...localDevHeader(), ...authHeader() };
}

function canUseStorage(): boolean {
  return typeof window !== "undefined" && Boolean(window.sessionStorage);
}

function cacheKey(path: string): string {
  return `${CACHE_PREFIX}${path}`;
}

export function getCachedJson<T>(path: string): T | null {
  if (!canUseStorage()) return null;
  try {
    const raw = window.sessionStorage.getItem(cacheKey(path));
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export function setCachedJson<T>(path: string, value: T): void {
  if (!canUseStorage()) return;
  try {
    window.sessionStorage.setItem(cacheKey(path), JSON.stringify(value));
  } catch {
    // cache is only used to keep the UI instant
  }
}

export function removeCachedJson(path: string): void {
  if (!canUseStorage()) return;
  try {
    window.sessionStorage.removeItem(cacheKey(path));
  } catch {
    // ignore cache failures
  }
}

function requestCanUseCache(path: string, options?: RequestInit): boolean {
  const method = (options?.method || "GET").toUpperCase();
  return method === "GET" && !options?.body && !path.startsWith("http");
}

export function userFacingApiError(status: number, rawMessage: string): string {
  const lower = rawMessage.toLowerCase();

  if (status === 401 || lower.includes("authentication") || lower.includes("unauthorized")) {
    return "Please sign in again.";
  }
  if (status === 403) return "This project is not available for this account.";
  if (status === 404 || lower.includes("not found")) return "This project data is not available.";
  if (status >= 500) return "Something went wrong. Please try again.";

  if (
    lower.includes("traceback") ||
    lower.includes("http") ||
    lower.includes("invalid document type") ||
    lower.includes("request failed")
  ) {
    return "This action could not be completed.";
  }

  return rawMessage || "This action could not be completed.";
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    if (typeof payload?.detail === "string") return payload.detail;
    if (typeof payload?.message === "string") return payload.message;
  } catch {
    // use status text below
  }
  return response.statusText || "Request failed.";
}

async function readResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) return undefined as T;

  const text = await response.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

export async function requestJson<T>(path: string, options?: RequestInit): Promise<T> {
  const useCache = requestCanUseCache(path, options);

  try {
    const response = await fetch(apiUrl(path), {
      ...options,
      headers: {
        ...(options?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...localDevHeader(),
        ...authHeader(),
        ...(options?.headers || {}),
      },
    });

    if (!response.ok) {
      const rawMessage = await readErrorMessage(response);
      const cached = useCache ? getCachedJson<T>(path) : null;
      if (cached) return cached;
      throw new ApiRequestError(response.status, userFacingApiError(response.status, rawMessage), rawMessage);
    }

    const data = await readResponse<T>(response);
    if (useCache) setCachedJson(path, data);
    return data;
  } catch (error) {
    const cached = useCache ? getCachedJson<T>(path) : null;
    if (cached) return cached;
    if (error instanceof ApiRequestError) throw error;
    throw new ApiRequestError(0, "Something went wrong. Please try again.", error instanceof Error ? error.message : undefined);
  }
}
