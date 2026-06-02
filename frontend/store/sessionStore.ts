'use client';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface User {
  id: string;
  email: string;
  name?: string;
  tier: string;
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

  // ── UI state persisted across navigation ──────────────────────────────────
  activeConversationId: string | null;

  // ── Conversation list (in-memory only, NOT persisted to localStorage) ─────
  conversations: Conversation[];

  // ── Actions ────────────────────────────────────────────────────────────────
  setSessionId: (id: string) => void;
  incrementMsg: () => void;
  incrementVideo: () => void;
  incrementQuiz: () => void;
  /** Reset counters on login so anonymous usage doesn't bleed through */
  setUser: (user: User, token: string) => void;
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
      activeConversationId: null,
      conversations:        [],

      setSessionId:            (id)    => set({ sessionId: id }),
      incrementMsg:            ()      => set((s) => ({ msgCount:   s.msgCount   + 1 })),
      incrementVideo:          ()      => set((s) => ({ videoCount: s.videoCount + 1 })),
      incrementQuiz:           ()      => set((s) => ({ quizCount:  s.quizCount  + 1 })),
      setUser:                 (u, t)  => set({ user: u, token: t, msgCount: 0, videoCount: 0, quizCount: 0 }),
      signOut:                 ()      => set({ user: null, token: null, activeConversationId: null, conversations: [] }),
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
      partialize: (s) => ({
        sessionId:            s.sessionId,
        msgCount:             s.msgCount,
        videoCount:           s.videoCount,
        quizCount:            s.quizCount,
        user:                 s.user,
        token:                s.token,
        activeConversationId: s.activeConversationId,
      }),
    }
  )
);
