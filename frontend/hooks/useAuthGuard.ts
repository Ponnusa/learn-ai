'use client';
import { useState } from 'react';
import { useSessionStore } from '@/store/sessionStore';

export function useAuthGuard() {
  const { user } = useSessionStore();
  const [showGate, setShowGate] = useState(false);

  function requireAuth(fn: () => void) {
    if (user) { fn(); } else { setShowGate(true); }
  }

  return { requireAuth, showGate, closeGate: () => setShowGate(false) };
}
