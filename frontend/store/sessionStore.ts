'use client';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface User {
  id: string;
  email: string;
  name?: string;
  tier: string;
}

interface SessionState {
  // Anonymous session
  sessionId: string | null;
  msgCount: number;
  videoCount: number;
  quizCount: number;
  // Registered user
  user: User | null;
  token: string | null;
  // Last-active conversation — survives cross-page navigation
  activeConversationId: string | null;
  // Actions
  setSessionId: (id: string) => void;
  incrementMsg: () => void;
  incrementVideo: () => void;
  incrementQuiz: () => void;
  setUser: (user: User, token: string) => void;
  signOut: () => void;
  setActiveConversationId: (id: string | null) => void;
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      sessionId: null,
      msgCount: 0,
      videoCount: 0,
      quizCount: 0,
      user: null,
      token: null,
      activeConversationId: null,
      setSessionId: (id) => set({ sessionId: id }),
      incrementMsg:   () => set((s) => ({ msgCount:   s.msgCount   + 1 })),
      incrementVideo: () => set((s) => ({ videoCount: s.videoCount + 1 })),
      incrementQuiz:  () => set((s) => ({ quizCount:  s.quizCount  + 1 })),
      // Reset counters on login so anonymous usage doesn't bleed through
      setUser: (user, token) => set({ user, token, msgCount: 0, videoCount: 0, quizCount: 0 }),
      signOut: () => set({ user: null, token: null, activeConversationId: null }),
      setActiveConversationId: (id) => set({ activeConversationId: id }),
    }),
    { name: 'learnai-session' }
  )
);
