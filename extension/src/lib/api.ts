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
  image_url?: string;
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

// ── Quiz ─────────────────────────────────────────────────────────────────

export interface QuizQuestion {
  q: string;
  options: string[];
  correct: number;
  explanation: string;
  difficulty: string;
}

export interface GenerateQuizRequest {
  topic: string;
  conversation_id?: string;
  session_id?: string;
  user_id?: string;
  language?: string;
  num_questions?: number;
}

export interface GenerateQuizResponse {
  quiz_id: string;
  questions: QuizQuestion[];
  message_id?: string | null;
}

export function generateQuiz(req: GenerateQuizRequest, token?: string | null): Promise<GenerateQuizResponse> {
  return request('POST', '/api/quizzes/generate', req, token);
}

// Per-question result shape matches backend/routers/quizzes.py's submit_quiz
// exactly: `correct` here is the CORRECT ANSWER'S INDEX (int), not a
// boolean — whether the student's own answer was right is `is_correct`.
export interface QuizResultItem {
  question: string;
  options: string[];
  correct: number;
  user_answer: number | null;
  is_correct: boolean;
  explanation: string;
}

export interface SubmitQuizResponse {
  correct: number;
  total: number;
  score_pct: number;
  results: QuizResultItem[];
  passed: boolean;
}

export function submitQuiz(
  quizId: string,
  answers: Record<number, number>,
  userId?: string | null,
  token?: string | null,
): Promise<SubmitQuizResponse> {
  return request('POST', `/api/quizzes/${quizId}/submit`, { answers, user_id: userId ?? undefined }, token);
}

// ── Auth (email/password — see App.tsx for why not magic-link/OAuth) ───────

export interface AuthUser {
  id: string;
  email: string;
  name: string | null;
  tier: string;
  account_type: string;
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
}

export function register(email: string, password: string, sessionId?: string | null): Promise<AuthResponse> {
  return request('POST', '/api/auth/register', { email, password, session_id: sessionId ?? undefined });
}

export function loginPassword(email: string, password: string): Promise<AuthResponse> {
  return request('POST', '/api/auth/login/password', { email, password });
}

// ── Text-to-speech (read aloud) ─────────────────────────────────────────

export async function getChatMessageAudio(messageId: string, language = 'en'): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/chat/messages/${messageId}/audio?language=${language}`);
  if (!res.ok) throw new Error('Audio generation failed');
  return res.blob();
}

// ── Screen-clip upload (ported from frontend/lib/api.ts's uploadRegionImage) ─

export async function uploadRegionImage(
  dataUrl: string,
  userId?: string,
  sessionId?: string,
  token?: string,
): Promise<string> {
  const blob = await fetch(dataUrl).then((r) => r.blob());
  const form = new FormData();
  form.append('file', blob, 'region.png');
  if (userId) form.append('user_id', userId);
  if (sessionId) form.append('session_id', sessionId);

  const headers: HeadersInit = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/uploads`, { method: 'POST', headers, body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Image upload failed');
  }
  const data = await res.json();
  return data.url as string;
}
