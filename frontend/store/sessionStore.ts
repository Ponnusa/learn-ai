'use client';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface User {
  id: string;
  email: string;
  name?: string;
  tier: string;
  theme?: 'dark' | 'light';
  language?: 'en' | 'fi' | 'sv' | 'es' | 'fr' | 'no';
  account_type?: 'student' | 'teacher' | 'institution_admin' | 'super_admin';
}

export interface Conversation {
  id: string;
  title: string;
  subject?: string;
  subtopic?: string;
  study_set_id?: string;
  study_set_title?: string;
  updated_at: string;
}

interface SessionState {
  // ── Anonymous session ──────────────────────────────────────────────────────
  sessionId: string | null;
  msgCount: number;
  videoCount: number;
  quizCount: number;

  // ── Registered user ────────────────────────────────────────────────────────
  user: User | null;
  token: string | null;
  /** Non-null when the user belongs to an institution that restricts available languages */
  institutionLanguages: string[] | null;

  // ── UI state persisted across navigation ──────────────────────────────────
  activeConversationId: string | null;

  // ── Conversation list (in-memory only, NOT persisted to localStorage) ─────
  conversations: Conversation[];

  // ── Hydration flag (not persisted) ───────────────────────────────────────
  // true once Zustand has finished reading localStorage on the client.
  // Auth guards must wait for this before redirecting, otherwise a refresh
  // fires the redirect before user is restored from storage.
  _hasHydrated: boolean;

  // ── Actions ────────────────────────────────────────────────────────────────
  setSessionId: (id: string) => void;
  incrementMsg: () => void;
  incrementVideo: () => void;
  incrementQuiz: () => void;
  /** Reset counters on login so anonymous usage doesn't bleed through */
  setUser: (user: User, token: string) => void;
  setInstitutionLanguages: (langs: string[] | null) => void;
  signOut: () => void;
  setActiveConversationId: (id: string | null) => void;
  setConversations: (convs: Conversation[]) => void;
  prependConversation: (conv: Conversation) => void;
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      sessionId:            null,
      msgCount:             0,
      videoCount:           0,
      quizCount:            0,
      user:                 null,
      token:                null,
      institutionLanguages: null,
      activeConversationId: null,
      conversations:        [],
      _hasHydrated:         false,

      setSessionId:            (id)    => set({ sessionId: id }),
      incrementMsg:            ()      => set((s) => ({ msgCount:   s.msgCount   + 1 })),
      incrementVideo:          ()      => set((s) => ({ videoCount: s.videoCount + 1 })),
      incrementQuiz:           ()      => set((s) => ({ quizCount:  s.quizCount  + 1 })),
      setUser:                 (u, t)  => set({ user: u, token: t, msgCount: 0, videoCount: 0, quizCount: 0 }),
      setInstitutionLanguages: (langs) => set({ institutionLanguages: langs }),
      signOut:                 ()      => set({ user: null, token: null, institutionLanguages: null, activeConversationId: null, conversations: [] }),
      setActiveConversationId: (id)    => set({ activeConversationId: id }),
      setConversations:        (convs) => set({ conversations: convs }),
      prependConversation:     (conv)  => set((s) => ({
        conversations: s.conversations.some(c => c.id === conv.id)
          ? s.conversations
          : [conv, ...s.conversations],
      })),
    }),
    {
      name: 'learnai-session',
      // conversations is large and fetched fresh from the API — don't persist it
      // _hasHydrated is runtime-only, never persisted
      partialize: (s) => ({
        sessionId:            s.sessionId,
        msgCount:             s.msgCount,
        videoCount:           s.videoCount,
        quizCount:            s.quizCount,
        user:                 s.user,
        token:                s.token,
        institutionLanguages: s.institutionLanguages,
        activeConversationId: s.activeConversationId,
      }),
      onRehydrateStorage: () => (state) => {
        if (state) state._hasHydrated = true;
      },
    }
  )
);
