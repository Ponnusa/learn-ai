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

// ── Auth (reuses the main app's magic-link endpoints directly) ────────────────

export interface SessionUser {
  id: string;
  email: string;
  name: string | null;
  tier: string;
  account_type: string;
}

export const sendMagicLink = (email: string) =>
  request<{ message: string; dev_url: string | null }>("POST", "/api/auth/magic-link", {
    email,
    // Must exactly match VIDEO_API_URL configured on the backend, or the
    // backend silently ignores it and points the email at the main app
    // instead (see auth.py's redirect_base allowlist check).
    redirect_base: typeof window !== "undefined" ? window.location.origin : undefined,
  });

export const verifyMagicLink = (token: string) =>
  request<{ token: string; user: SessionUser }>("POST", "/api/auth/verify", { token });

// ── Developer platform (session-auth) ──────────────────────────────────────────

export interface ApiKeyStatus {
  has_key: boolean;
  id?: string;
  status?: "pending" | "approved" | "revoked";
  label?: string;
  created_at?: string;
  approved_at?: string | null;
  revoked_at?: string | null;
}

export interface ApiKeyCreated {
  id: string;
  status: string;
  created_at: string;
  api_key: string; // shown once
  masked: string;
}

export const getMyApiKey = (token: string) =>
  request<ApiKeyStatus>("GET", "/api/developer/api-key", undefined, token);

export const requestApiKey = (label: string, token: string) =>
  request<ApiKeyCreated>("POST", "/api/developer/api-key/request", { label }, token);

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
  label: string | null;
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
