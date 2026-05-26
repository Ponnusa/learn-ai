const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function getHeaders(token?: string | null): HeadersInit {
  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
  };
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  token?: string | null,
): Promise<T> {
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

const get  = <T>(path: string, token?: string | null) => request<T>('GET',    path, undefined, token);
const post = <T>(path: string, body: unknown, token?: string | null) => request<T>('POST',   path, body, token);
const put  = <T>(path: string, body: unknown, token?: string | null) => request<T>('PUT',    path, body, token);
const del  = <T>(path: string, token?: string | null) => request<T>('DELETE', path, undefined, token);

// ── Auth ──────────────────────────────────────────────────────────────────────
export const sendMagicLink = (email: string, sessionId?: string, knowledgeLevel?: string) =>
  post('/api/auth/magic-link', { email, session_id: sessionId, knowledge_level: knowledgeLevel });

export const verifyMagicLink = (token: string) =>
  post<{ token: string; user: { id: string; email: string; name: string; tier: string } }>(
    '/api/auth/verify', { token }
  );

// ── Sessions ──────────────────────────────────────────────────────────────────
export const createSession = (sessionId?: string) =>
  post<{ session_id: string; msg_count: number; video_count: number; quiz_count: number }>(
    '/api/sessions', { session_id: sessionId }
  );

export const getSessionUsage = (sessionId: string) =>
  get<{ msg_count: number; video_count: number; quiz_count: number; converted: boolean }>(
    `/api/sessions/${sessionId}/usage`
  );

// ── Chat ──────────────────────────────────────────────────────────────────────
export const createConversation = (userId?: string, sessionId?: string, token?: string) =>
  post<{ conversation_id: string }>('/api/chat/conversations', { user_id: userId, session_id: sessionId }, token);

export const listConversations = (userId?: string, sessionId?: string, token?: string) =>
  get<any[]>(`/api/chat/conversations?${userId ? `user_id=${userId}` : `session_id=${sessionId}`}`, token);

export const getMessages = (conversationId: string, token?: string) =>
  get<any[]>(`/api/chat/conversations/${conversationId}/messages`, token);

export const sendMessage = (data: {
  message: string;
  conversation_id?: string;
  image_url?: string;
  user_id?: string;
  session_id?: string;
  language?: string;
}, token?: string) => post<{
  conversation_id: string;
  message_id: string;
  reply: string;
  chips: string[];
  subject: { subject: string; subtopic: string; icon: string } | null;
}>('/api/chat/send', data, token);

// ── Videos ────────────────────────────────────────────────────────────────────
export const generateVideo = (data: {
  prompt: string;
  conversation_id?: string;
  message_id?: string;
  user_id?: string;
  session_id?: string;
  subject?: string;
  language?: string;
  aspect_ratio?: string;
}, token?: string) => post<{ supported: boolean; video_id?: number; status?: string; message?: string }>(
  '/api/videos/generate', data, token
);

export const getVideoStatus = (videoId: number, token?: string) =>
  get<{ id: number; status: string; video_url?: string; error_message?: string }>(
    `/api/videos/${videoId}/status`, token
  );

export const getUserVideos = (userId: string, token?: string) =>
  get<any[]>(`/api/videos/user/${userId}`, token);

export const getConversationVideos = (conversationId: string, token?: string) =>
  get<{ id: number; message_id: string; status: string; video_url?: string }[]>(
    `/api/videos/conversation/${conversationId}`, token
  );

// ── Quizzes ───────────────────────────────────────────────────────────────────
export const getQuiz = (quizId: string, token?: string) =>
  get<{
    quiz_id: string;
    questions: any[];
    subject?: string;
    completed: boolean;
    score?: number | null;
    max_score?: number | null;
    user_answers?: Record<string, number>;
  }>(`/api/quizzes/${quizId}`, token);

export const generateQuiz = (data: {
  topic: string;
  conversation_id?: string;
  user_id?: string;
  session_id?: string;
  subject?: string;
  language?: string;
  num_questions?: number;
}, token?: string) => post<{ quiz_id: string; questions: any[]; message_id?: string | null }>('/api/quizzes/generate', data, token);

export const submitQuiz = (quizId: string, answers: Record<string, number>, userId?: string, token?: string) =>
  post<{ correct: number; total: number; score_pct: number; results: any[]; passed: boolean }>(
    `/api/quizzes/${quizId}/submit`, { answers, user_id: userId }, token
  );

// ── File upload (multipart) ───────────────────────────────────────────────────
export async function uploadFile(file: File, sessionId?: string, userId?: string, token?: string) {
  const form = new FormData();
  form.append('file', file);
  if (sessionId) form.append('session_id', sessionId);
  if (userId)    form.append('user_id',    userId);
  const res = await fetch(`${API_BASE}/api/uploads`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) throw new Error('Upload failed');
  return res.json();
}
