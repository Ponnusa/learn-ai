"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { SessionUser } from "./api";

interface SessionState {
  token: string | null;
  user: SessionUser | null;
  // False until the persisted session has been read back from localStorage.
  // On a hard refresh the store starts empty and rehydrates asynchronously —
  // anything gating a page on `token` (see RequireAuth) must wait for this
  // to flip true before deciding to redirect, or it'll bounce an already
  // logged-in user to /login because it checked before the real value loaded.
  hasHydrated: boolean;
  setSession: (token: string, user: SessionUser) => void;
  clearSession: () => void;
  setHasHydrated: (state: boolean) => void;
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      hasHydrated: false,
      setSession: (token, user) => set({ token, user }),
      clearSession: () => set({ token: null, user: null }),
      setHasHydrated: (state) => set({ hasHydrated: state }),
    }),
    {
      name: "video-api-session",
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    }
  )
);
