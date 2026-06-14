'use client';
/**
 * Google OAuth callback page.
 * Google redirects here with ?code=...&state=...
 * We send the code to the backend, get a JWT, store it, redirect home.
 */
import { useEffect, useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Loader2, XCircle } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function CallbackContent() {
  const searchParams = useSearchParams();
  const router       = useRouter();
  const { setUser, sessionId } = useSessionStore();
  const [error, setError] = useState('');

  useEffect(() => {
    const code  = searchParams.get('code');
    const state = searchParams.get('state');
    const err   = searchParams.get('error');

    if (err) {
      setError('Google sign-in was cancelled or denied.');
      return;
    }
    if (!code) {
      setError('No auth code received from Google.');
      return;
    }

    // Optional CSRF check
    const savedState = sessionStorage.getItem('oauth_state');
    if (savedState && state && savedState !== state) {
      setError('State mismatch — possible CSRF. Please try again.');
      return;
    }
    sessionStorage.removeItem('oauth_state');

    fetch(`${API_BASE}/api/auth/google/callback`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ code, session_id: sessionId }),
    })
      .then(r => r.json().then(d => ({ ok: r.ok, data: d })))
      .then(({ ok, data }) => {
        if (!ok) throw new Error(data.detail || 'Google sign-in failed');
        setUser(data.user, data.token);
        const dest = data.user.account_type === 'super_admin'
          ? '/admin'
          : data.user.account_type === 'institution_admin'
            ? '/institution/dashboard'
            : data.user.account_type === 'teacher'
              ? '/teacher/dashboard'
              : '/';
        router.replace(dest);
      })
      .catch(e => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="min-h-screen bg-[#0f0f0f] flex items-center justify-center p-4">
        <div className="text-center max-w-sm">
          <XCircle size={40} className="text-red-400 mx-auto mb-4" />
          <p className="text-white font-semibold mb-2">Sign-in failed</p>
          <p className="text-white/50 text-sm mb-6">{error}</p>
          <button onClick={() => router.push('/auth/login')}
            className="px-5 py-2.5 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl transition-colors">
            Back to login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0f0f0f] flex items-center justify-center">
      <div className="text-center">
        <Loader2 size={36} className="text-purple-400 animate-spin mx-auto mb-4" />
        <p className="text-white font-medium">Completing sign-in…</p>
        <p className="text-white/40 text-sm mt-1">Just a moment</p>
      </div>
    </div>
  );
}

export default function CallbackPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#0f0f0f] flex items-center justify-center">
        <Loader2 size={32} className="text-purple-400 animate-spin" />
      </div>
    }>
      <CallbackContent />
    </Suspense>
  );
}
