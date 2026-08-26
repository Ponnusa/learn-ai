const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  method: "GET" | "POST",
  path: string,
  body?: unknown,
  token?: string
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiError(res.status, data.detail || `Request failed (${res.status})`);
  }
  return data as T;
}

// ── Auth ────────────────────────────────────────────────────────────────────
// Login reuses the main app's existing password endpoint unchanged. Signup is
// specific to this app: it creates the account AND the first (pending) API
// key request in one call, collecting company name/description up front
// instead of as a separate dashboard step. See developer_api.py's
// developer_signup() for why there's no email-ownership verification step
// here (the superadmin approval gate is the real trust boundary).

export interface SessionUser {
  id: string;
  email: string;
  name: string | null;
  tier: string;
  account_type: string;
}

export const login = (email: string, password: string) =>
  request<{ token: string; user: SessionUser }>("POST", "/api/auth/login/password", { email, password });

export interface ApiKeyCreated {
  id: string;
  status: string;
  created_at: string;
  api_key: string; // shown once
  masked: string;
}

export const signup = (email: string, password: string, companyName: string, description: string) =>
  request<{ token: string; user: SessionUser; api_key: ApiKeyCreated }>("POST", "/api/developer/signup", {
    email,
    password,
    company_name: companyName,
    description,
  });

// ── Developer platform (session-auth) ──────────────────────────────────────────

export interface ApiKeyStatus {
  has_key: boolean;
  id?: string;
  status?: "pending" | "approved" | "revoked";
  company_name?: string;
  description?: string;
  created_at?: string;
  approved_at?: string | null;
  revoked_at?: string | null;
}

export const getMyApiKey = (token: string) =>
  request<ApiKeyStatus>("GET", "/api/developer/api-key", undefined, token);

export const requestApiKey = (companyName: string, description: string, token: string) =>
  request<ApiKeyCreated>(
    "POST",
    "/api/developer/api-key/request",
    { company_name: companyName, description },
    token
  );

export interface VideoRecord {
  id: number;
  status: string;
  video_url: string | null;
  thumbnail_url: string | null;
  prompt: string;
  subject: string | null;
  language: string;
  duration_secs: number | null;
  created_at: string;
  error_message: string | null;
}

export const listMyVideos = (token: string) =>
  request<VideoRecord[]>("GET", "/api/developer/videos", undefined, token);

export interface GenerateVideoBody {
  topic: string;
  subject?: string;
  language?: string;
  aspect_ratio?: string;
}

export const generateVideo = (body: GenerateVideoBody, token: string) =>
  request<{ video_id: number; status: string }>("POST", "/api/developer/videos/generate", body, token);

// ── Admin (session-auth, superadmin only) ──────────────────────────────────────

export interface DeveloperKeyAdminRow {
  id: string;
  status: "pending" | "approved" | "revoked";
  company_name: string | null;
  description: string | null;
  created_at: string;
  approved_at: string | null;
  revoked_at: string | null;
  email: string;
  name: string | null;
  videos_generated: number;
}

export const listDeveloperKeys = (token: string) =>
  request<DeveloperKeyAdminRow[]>("GET", "/api/admin/developer-keys", undefined, token);

export const approveDeveloperKey = (keyId: string, token: string) =>
  request<{ id: string; status: string }>("POST", `/api/admin/developer-keys/${keyId}/approve`, undefined, token);

export const revokeDeveloperKey = (keyId: string, token: string) =>
  request<{ id: string; status: string }>("POST", `/api/admin/developer-keys/${keyId}/revoke`, undefined, token);
