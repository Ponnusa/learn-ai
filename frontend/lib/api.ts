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
  post<{ token: string; user: { id: string; email: string; name: string; tier: string; account_type?: 'student' | 'teacher' | 'institution_admin' | 'super_admin' } }>(
    '/api/auth/verify', { token }
  );

export const getUserStats = (userId: string, token?: string) =>
  get<{
    messages:      number;
    videos:        number;
    quizzes:       number;
    conversations: number;
    top_subject:   string | null;
    member_since:  string | null;
  }>(`/api/auth/stats?user_id=${userId}`, token);

export const getUserLimits = (userId: string, token?: string) =>
  get<{
    tier: string;
    limits: {
      messages_daily: number;
      videos_daily:   number;
      images_daily:   number;
      quiz_daily:     number;
    };
    usage_today: {
      messages: number;
      videos:   number;
      images:   number;
      quizzes:  number;
    };
  }>(`/api/auth/limits?user_id=${userId}`, token);

export type StudentProfile = {
  grade:              string | null;
  goal:               string | null;
  subject_confidence: Record<string, string>;
};

export const updateTheme = (userId: string, theme: 'dark' | 'light', token?: string) =>
  request<{ ok: boolean }>('PATCH', '/api/auth/theme', { user_id: userId, theme }, token);

export const updateLanguage = (userId: string, language: 'en' | 'fi' | 'sv', token?: string) =>
  request<{ ok: boolean }>('PATCH', '/api/auth/language', { user_id: userId, language }, token);

export const getStudentProfile = (userId: string, token?: string) =>
  get<StudentProfile>(`/api/auth/profile?user_id=${userId}`, token);

export const updateStudentProfile = (
  data: { user_id: string; grade?: string | null; goal?: string | null; subject_confidence?: Record<string, string> },
  token?: string,
) => {
  const { user_id, ...rest } = data;
  return request<{ ok: boolean }>('PATCH', '/api/auth/profile', { user_id, ...rest }, token);
};

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

type DebugPromptResponse = {
  model: string;
  system_prompt: string;
  system_prompt_chars: number;
  material_chars?: number;
  history: { role: string; content: string }[];
  history_count: number;
  conversation_id: string | null;
  subject?: string | null;
};

export const debugChatPrompt = (data: {
  message: string;
  conversation_id?: string;
  user_id?: string;
  session_id?: string;
  language?: string;
}, token?: string) =>
  post<DebugPromptResponse>('/api/chat/debug-prompt', data, token);

export const debugStudysetPrompt = (studySetId: string, data: {
  message: string;
  conversation_id?: string;
  user_id?: string;
  session_id?: string;
}, token?: string) =>
  post<DebugPromptResponse>(`/api/studysets/${studySetId}/debug-prompt`, data, token);

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
  get<{
    id: number;
    status: string;
    video_url?: string;
    error_message?: string;
    transcript_markdown?: string;
    verified_solution?: string;
    prompt?: string;
  }>(`/api/videos/${videoId}/status`, token);

export const retryVideoManim = (videoId: number, token?: string) =>
  post<{ status: string; video_id: number }>(
    `/api/videos/${videoId}/retry-manim`, {}, token
  );

export const regenerateVideo = (videoId: number, token?: string) =>
  post<{ status: string; video_id: number }>(
    `/api/videos/${videoId}/regenerate`, {}, token
  );

export const deleteVideo = (videoId: number, token?: string) =>
  del<{ deleted: boolean }>(`/api/videos/${videoId}`, token);

export const getSessionVideos = (sessionId: string) =>
  get<{
    id: number;
    status: string;
    video_url?: string;
    thumbnail_url?: string;
    prompt?: string;
    subject?: string;
    duration_secs?: number;
    created_at: string;
    transcript_markdown?: string;
    conversation_id?: string;
    message_id?: string;
  }[]>(`/api/videos/session/${sessionId}`);

export const getUserVideos = (userId: string, token?: string) =>
  get<{
    id: number;
    status: string;
    video_url?: string;
    thumbnail_url?: string;
    prompt?: string;
    subject?: string;
    duration_secs?: number;
    created_at: string;
    transcript_markdown?: string;
    conversation_id?: string;
    message_id?: string;
  }[]>(`/api/videos/user/${userId}`, token);

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

// ── StudySets ─────────────────────────────────────────────────────────────────

export type StudySetSummary = {
  id: string; title: string; subject?: string; status: string;
  summary?: string; created_at: string;
  concept_count: number; flashcard_count: number;
};

export type StudyConcept = {
  id: string; name: string; definition: string; explanation?: string; order_index: number;
};

export type StudyFlashcard = {
  id: string; front: string; back: string; order_index: number; is_due?: boolean;
};

export type StudyMaterial = {
  id: string; filename: string; page_count?: number;
  char_count?: number; status: string; error_msg?: string; created_at: string;
  file_url?: string;
};

export type StudySetDetail = StudySetSummary & {
  description?: string; updated_at: string;
  concepts: StudyConcept[]; flashcards: StudyFlashcard[]; materials: StudyMaterial[];
};

export const createStudySet = (data: {
  title: string; subject?: string; description?: string;
  user_id?: string; session_id?: string;
}, token?: string) =>
  post<StudySetSummary>('/api/studysets', data, token);

export const listStudySets = (userId?: string, sessionId?: string, token?: string) => {
  if (!userId && !sessionId) return Promise.resolve<StudySetSummary[]>([]);
  const param = userId ? `user_id=${userId}` : `session_id=${sessionId}`;
  return get<StudySetSummary[]>(`/api/studysets?${param}`, token);
};

export const getStudySet = (id: string, token?: string, userId?: string) =>
  get<StudySetDetail>(`/api/studysets/${id}${userId ? `?user_id=${userId}` : ''}`, token);

export const extractStudySetConcepts = (id: string, token?: string) =>
  post<{ concepts: number; flashcards_added: number }>(`/api/studysets/${id}/extract-concepts`, {}, token);

export const getStudySetStatus = (id: string, token?: string) =>
  get<{ status: string; summary?: string; concept_count: number; flashcard_count: number }>(
    `/api/studysets/${id}/status`, token
  );

export async function uploadStudyMaterial(
  studySetId: string, file: File, userId?: string, token?: string,
) {
  const form = new FormData();
  form.append('file', file);
  if (userId) form.append('user_id', userId);
  const res = await fetch(`${API_BASE}/api/studysets/${studySetId}/upload`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || 'Upload failed'); }
  return res.json() as Promise<{ material_id: string; status: string }>;
}

export const chatWithStudySet = (
  id: string,
  message: string,
  history: {role: string; content: string}[],
  token?: string,
  conceptName?: string,
  conversationId?: string,
  userId?: string,
  sessionId?: string,
  imageUrl?: string,
  language?: string,
  studyConceptId?: string | null,
) =>
  post<{ reply: string; chips: string[]; conversation_id: string; message_id: string }>(
    `/api/studysets/${id}/chat`,
    {
      message,
      history,
      concept_name:      conceptName     ?? null,
      conversation_id:   conversationId  ?? null,
      user_id:           userId          ?? null,
      session_id:        sessionId       ?? null,
      image_url:         imageUrl        ?? null,
      language:          language        ?? 'en',
      study_concept_id:  studyConceptId  ?? null,
    },
    token,
  );

/**
 * Upload a canvas region (base64 data URL) to R2 via /api/uploads.
 * Returns the public R2 URL for use as image_url in chat messages.
 */
export async function uploadRegionImage(
  dataUrl: string,
  userId?: string,
  sessionId?: string,
  token?: string,
): Promise<string> {
  const blob = await fetch(dataUrl).then(r => r.blob());
  const form = new FormData();
  form.append('file', blob, 'region.png');
  if (userId)    form.append('user_id',    userId);
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

export type StudySetConversation = {
  id: string;
  title: string;
  created_at: string;
  study_concept_id?: string | null;
  message_count: number;
  video_count: number;
  quiz_count: number;
};

export const getStudySetConversations = (studySetId: string, token?: string) =>
  get<StudySetConversation[]>(`/api/studysets/${studySetId}/conversations`, token);

export const reviewStudyCard = (studySetId: string, cardId: string, userId: string, rating: number, token?: string) =>
  post<{ ok: boolean }>(`/api/studysets/${studySetId}/cards/${cardId}/review`, { user_id: userId, rating }, token);

export const deleteStudySet = (id: string, token?: string) =>
  del<{ ok: boolean }>(`/api/studysets/${id}`, token);

// ── Educational Images ────────────────────────────────────────────────────────

export type EduImageJob = {
  id?: string;
  jobId?: string;
  concept: string;
  domain?: string;
  diagram_type?: string;
  /** Backward-compatible spec — has visual_elements for display */
  spec?: {
    visual_elements?: string[];
    key_relationships?: string;
    title?: string;
    difficulty?: string;
    [k: string]: unknown;
  };
  /** Rich knowledge model from knowledge extractor */
  knowledge_model?: {
    learning_goal?: string;
    entities?: string[];
    mechanisms?: string[];
    must_show?: string[];
    common_misconceptions?: string[];
    [k: string]: unknown;
  };
  /** Critic report from GPT-4o vision review */
  critic_report?: {
    score?: number;
    issues?: string[];
    regenerate?: boolean;
    attempt?: number;
    [k: string]: unknown;
  };
  generation_attempts?: number;
  /** AI-generated markdown explanation — shown as a text message alongside the image */
  description?: string;
  prompt?: string;
  image_url?: string;
  status: 'processing' | 'ready' | 'failed';
  error_msg?: string;
  message_id?: string;
  conversation_id?: string;
  study_set_id?: string;
  created_at?: string;
};

export const generateEduImage = (data: {
  concept: string;
  user_id?: string;
  session_id?: string;
  conversation_id?: string;
  study_set_id?: string;
  message_id?: string;
}, token?: string) =>
  post<{ jobId: string; status: string }>('/api/images/generate', data, token);

export const getEduImageJob = (jobId: string, token?: string) =>
  get<EduImageJob>(`/api/images/${jobId}`, token);

export const listEduImages = (params: {
  user_id?: string;
  session_id?: string;
  conversation_id?: string;
  study_set_id?: string;
}, token?: string) => {
  const q = new URLSearchParams();
  if (params.conversation_id) q.set('conversation_id', params.conversation_id);
  else if (params.study_set_id) q.set('study_set_id', params.study_set_id);
  else if (params.user_id) q.set('user_id', params.user_id);
  else if (params.session_id) q.set('session_id', params.session_id);
  return get<EduImageJob[]>(`/api/images?${q}`, token);
};

export const deleteEduImage = (jobId: string, token?: string) =>
  del<{ deleted: boolean }>(`/api/images/${jobId}`, token);

export const retryEduImage = (jobId: string, token?: string) =>
  post<{ jobId: string; status: string }>(`/api/images/${jobId}/retry`, {}, token);

/** Fetch a study-set PDF.
 *  1. If R2 URL is known, proxy it through the Next.js API route (avoids R2 CORS restrictions).
 *  2. Fall back to the Railway backend proxy (reads file_data from DB). */
export async function fetchMaterialPdf(
  studySetId: string,
  materialId: string,
  filename: string,
  token?: string,
  fileUrl?: string,
): Promise<File> {
  // Next.js server-side proxy — fetches R2 server-side so CORS never applies
  if (fileUrl) {
    try {
      const proxyRes = await fetch(`/api/pdf-proxy?url=${encodeURIComponent(fileUrl)}`);
      if (proxyRes.ok) {
        const blob = await proxyRes.blob();
        return new File([blob], filename, { type: 'application/pdf' });
      }
    } catch {
      // network error — fall through to Railway proxy
    }
  }

  // Railway backend proxy fallback (reads file_data from DB)
  const res = await fetch(
    `${API_BASE}/api/studysets/${studySetId}/materials/${materialId}/pdf`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} },
  );
  if (!res.ok) {
    let detail = 'Could not load PDF';
    try { detail = (await res.json()).detail ?? detail; } catch {}
    throw new Error(detail);
  }
  const blob = await res.blob();
  return new File([blob], filename, { type: 'application/pdf' });
}

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
