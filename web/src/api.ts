// The web app talks only to the gateway (FR-10.1).

const raw = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
// Render passes the API's host without a scheme.
export const API_URL = raw.startsWith("http") ? raw : `https://${raw}`;

const STORE = "boardroom.session";

export type Role = "owner" | "ceo" | "department_lead" | "contributor" | "investor";

export const ROLE_NAMES: Record<Role, string> = {
  owner: "Owner",
  ceo: "CEO",
  department_lead: "Department lead",
  contributor: "Contributor",
  investor: "Investor",
};

export const DEPARTMENTS = ["finance", "sales", "delivery", "people", "plan"] as const;
export const DEPARTMENT_NAMES: Record<string, string> = {
  finance: "Finance",
  sales: "Sales pipeline",
  delivery: "Product delivery",
  people: "People",
  plan: "Plan",
};

export interface Tokens {
  access_token: string;
  refresh_token: string;
  tenant_id?: string | null;
}

export interface Membership {
  tenant_id: string;
  tenant_name: string;
  tenant_type: string;
  role: Role;
  departments: string[];
}

export interface Me {
  id: string;
  email: string;
  name: string;
  memberships: Membership[];
}

export interface Person {
  user_id: string;
  name: string;
  email: string | null;
  role: Role;
  departments: string[];
}

export interface Invitation {
  id: string;
  email: string;
  role: Role;
  departments: string[];
  expires_at: string;
}

export interface Permissions {
  role: Role;
  actions: string[];
  can_approve: boolean;
}

export interface Approval {
  roles: string[];
  user_ids: string[];
}

export interface AuditEntry {
  id: string;
  action: string;
  actor_user_id: string | null;
  target_type: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function load(): Tokens | null {
  try {
    const value = localStorage.getItem(STORE);
    return value ? (JSON.parse(value) as Tokens) : null;
  } catch {
    return null;
  }
}

let session: Tokens | null = load();

export function saveSession(tokens: Tokens | null): void {
  session = tokens;
  try {
    if (tokens) localStorage.setItem(STORE, JSON.stringify(tokens));
    else localStorage.removeItem(STORE);
  } catch {
    // Private windows can refuse storage. The session then lasts for this page only.
  }
}

export function signedIn(): boolean {
  return session !== null;
}

function message(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return "Check the highlighted details and try again.";
  return status >= 500 ? "Something went wrong on our side. Try again in a moment." : "That did not work.";
}

async function refreshTokens(): Promise<boolean> {
  if (!session) return false;
  const r = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: session.refresh_token }),
  });
  if (!r.ok) {
    saveSession(null);
    return false;
  }
  saveSession(await r.json());
  return true;
}

export async function api<T>(
  path: string,
  options: { method?: string; body?: unknown; tenant?: string; retry?: boolean } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (session) headers.Authorization = `Bearer ${session.access_token}`;
  if (options.tenant) headers["X-Tenant-ID"] = options.tenant;
  const r = await fetch(`${API_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  if (r.status === 401 && session && options.retry !== false && (await refreshTokens())) {
    return api<T>(path, { ...options, retry: false });
  }
  if (r.status === 204) return undefined as T;
  const body = await r.json().catch(() => null);
  if (!r.ok) throw new ApiError(r.status, message(body, r.status));
  return body as T;
}

export async function signOut(): Promise<void> {
  if (session) {
    await fetch(`${API_URL}/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: session.refresh_token }),
    }).catch(() => undefined);
  }
  saveSession(null);
}
