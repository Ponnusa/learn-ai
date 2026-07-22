'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

interface AuthGuardProps {
  children: React.ReactNode;
  requireRole?: string[];
  loginPath?: string;
}

/**
 * Wraps protected layout content.
 * Waits for Zustand to rehydrate from localStorage (_hasHydrated) before
 * checking auth — without this, a page refresh fires the redirect before
 * the stored user is restored, sending logged-in users back to login.
 */
export function AuthGuard({ children, requireRole, loginPath = '/auth/login' }: AuthGuardProps) {
  const router = useRouter();
  const { user, _hasHydrated } = useSessionStore();

  useEffect(() => {
    if (!_hasHydrated) return;
    if (!user) { router.replace(loginPath); return; }
    if (requireRole && !requireRole.includes(user.account_type ?? '')) {
      router.replace('/');
    }
  }, [_hasHydrated, user]);

  if (!_hasHydrated) {
    return (
      <div className="flex h-screen items-center justify-center bg-[var(--bg)]">
        <Loader2 size={22} className="animate-spin text-purple-400" />
      </div>
    );
  }

  if (!user) return null;
  if (requireRole && !requireRole.includes(user.account_type ?? '')) return null;

  return <>{children}</>;
}
