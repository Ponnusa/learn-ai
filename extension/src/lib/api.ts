// Trimmed port of frontend/lib/api.ts — same request/response shapes, same
// Bearer-token/no-cookie auth pattern. Called directly from the side panel
// page (a genuine chrome-extension://<id> origin), not from the content
// script — content-script fetch() calls are attributed to the *host page's*
// origin in MV3, not the extension's, so they'd fail this backend's CORS
// allow-list and would be the wrong pattern regardless. The panel is a real
// extension page, so it can call the backend directly.

const API_BASE = 'https://learn-ai-production.up.railway.app';

function getHeaders(token?: string | null): HeadersInit {
  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
  };
}

async function request<T>(method: string, path: string, body?: unknown, token?: string | null): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: getHeaders(token),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

export interface SessionResponse {
  session_id: string;
  msg_count: number;
  video_count: number;
  quiz_count: number;
  upload_count: number;
  converted: boolean;
}

export function createOrGetSession(sessionId?: string | null): Promise<SessionResponse> {
  return request('POST', '/api/sessions', { session_id: sessionId ?? undefined });
}

export interface ChatSubject {
  subject: string;
  subtopic: string;
  icon: string;
}

export interface SendMessageRequest {
  message: string;
  conversation_id?: string;
  session_id?: string;
  user_id?: string;
  language?: string;
  source?: 'app' | 'extension';
}

export interface SendMessageResponse {
  conversation_id: string;
  message_id: string;
  reply: string;
  chips: string[];
  subject: ChatSubject | null;
  ladder_depth?: number | null;
}

export function sendMessage(req: SendMessageRequest, token?: string | null): Promise<SendMessageResponse> {
  return request('POST', '/api/chat/send', { ...req, source: req.source ?? 'extension' }, token);
}
