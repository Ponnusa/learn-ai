'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Mail, Lock, User, Eye, EyeOff, ArrowRight, Loader2, CheckCircle } from 'lucide-react';
import { sendMagicLink, verifyMagicLink } from '@/lib/api';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type Method = 'magic' | 'password';
type PwdMode = 'signin' | 'register';

export default function LoginPage() {
  const router = useRouter();
  const { setUser, sessionId } = useSessionStore();

  const [method,    setMethod]    = useState<Method>('magic');
  const [pwdMode,   setPwdMode]   = useState<PwdMode>('signin');
  const [email,     setEmail]     = useState('');
  const [password,  setPassword]  = useState('');
  const [name,      setName]      = useState('');
  const [showPwd,   setShowPwd]   = useState(false);
  const [loading,   setLoading]   = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error,     setError]     = useState('');
  const [magicSent, setMagicSent] = useState(false);

  // ── Magic link ──────────────────────────────────────────────────────────────
  async function handleMagicLink(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;
    setLoading(true); setError('');
    try {
      await sendMagicLink(email, sessionId ?? undefined);
      setMagicSent(true);
    } catch (err: any) {
      setError(err.message || 'Failed to send magic link');
    } finally {
      setLoading(false);
    }
  }

  // ── Password sign-in / register ─────────────────────────────────────────────
  async function handlePassword(e: React.FormEvent) {
    e.preventDefault();
    if (!email || !password) return;
    setLoading(true); setError('');
    try {
      const endpoint = pwdMode === 'register' ? '/api/auth/register' : '/api/auth/login/password';
      const body: any = { email, password };
      if (pwdMode === 'register' && name) body.name = name;
      if (sessionId) body.session_id = sessionId;

      const res  = await fetch(`${API_BASE}${endpoint}`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Authentication failed');

      setUser(data.user, data.token);
      router.replace('/');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  // ── Google OAuth ────────────────────────────────────────────────────────────
  async function handleGoogle() {
    setGoogleLoading(true); setError('');
    try {
      const res  = await fetch(`${API_BASE}/api/auth/google`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Google login not available');
      // Store state for CSRF check in callback page
      sessionStorage.setItem('oauth_state', data.state);
      window.location.href = data.url;
    } catch (err: any) {
      setError(err.message);
      setGoogleLoading(false);
    }
  }

  // ── Magic-sent confirmation ─────────────────────────────────────────────────
  if (magicSent) {
    return (
      <div className="min-h-screen bg-[#0f0f0f] flex items-center justify-center p-4">
        <div className="text-center max-w-sm">
          <CheckCircle size={48} className="text-green-400 mx-auto mb-4" />
          <h2 className="text-white text-xl font-bold mb-2">Check your inbox</h2>
          <p className="text-white/50 text-sm mb-6">
            We sent a sign-in link to <span className="text-white/80">{email}</span>.
            It expires in 15 minutes.
          </p>
          <button
            onClick={() => setMagicSent(false)}
            className="text-purple-400 hover:text-purple-300 text-sm underline"
          >
            Use a different email
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0f0f0f] flex items-center justify-center p-4">
      <div className="w-full max-w-sm">

        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center text-white text-2xl font-bold mx-auto mb-4 shadow-lg shadow-purple-500/20">
            L
          </div>
          <h1 className="text-white text-xl font-bold">Sign in to Learn-AI</h1>
          <p className="text-white/40 text-sm mt-1">Continue your learning journey</p>
        </div>

        {/* Card */}
        <div className="bg-[#1a1a1a] border border-white/10 rounded-2xl p-6 shadow-xl">

          {/* Google button */}
          <button
            onClick={handleGoogle}
            disabled={googleLoading}
            className="w-full flex items-center justify-center gap-3 py-2.5 rounded-xl border border-white/15
                       bg-white/5 hover:bg-white/10 text-white text-sm font-medium transition-all
                       disabled:opacity-50"
          >
            {googleLoading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <svg width="18" height="18" viewBox="0 0 48 48">
                <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.2l6.7-6.7C35.8 2.5 30.3 0 24 0 14.7 0 6.7 5.4 2.8 13.3l7.8 6C12.3 13 17.7 9.5 24 9.5z"/>
                <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v8.5h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8C43.7 37.3 46.5 31.4 46.5 24.5z"/>
                <path fill="#FBBC05" d="M10.6 28.7A14.6 14.6 0 0 1 9.5 24c0-1.6.3-3.2.8-4.7l-7.8-6A23.9 23.9 0 0 0 0 24c0 3.9.9 7.5 2.5 10.7l8.1-6z"/>
                <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.8 2.2-8.4 2.2-6.3 0-11.7-4.3-13.6-10l-8.1 6C6.5 42.6 14.7 48 24 48z"/>
              </svg>
            )}
            Continue with Google
          </button>

          {/* Divider */}
          <div className="flex items-center gap-3 my-5">
            <div className="flex-1 h-px bg-white/10" />
            <span className="text-white/30 text-xs">or</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          {/* Method tabs */}
          <div className="flex rounded-xl bg-white/5 p-1 mb-5">
            {(['magic', 'password'] as Method[]).map(m => (
              <button
                key={m}
                onClick={() => { setMethod(m); setError(''); }}
                className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${
                  method === m
                    ? 'bg-purple-600 text-white shadow'
                    : 'text-white/40 hover:text-white/70'
                }`}
              >
                {m === 'magic' ? '✉️ Magic link' : '🔑 Password'}
              </button>
            ))}
          </div>

          {/* Magic link form */}
          {method === 'magic' && (
            <form onSubmit={handleMagicLink} className="space-y-3">
              <div className="relative">
                <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
                <input
                  type="email" value={email} onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com" required
                  className="w-full bg-white/5 border border-white/10 rounded-xl pl-9 pr-4 py-2.5 text-sm text-white placeholder-white/25 outline-none focus:border-purple-500/60 transition-colors"
                />
              </div>
              {error && <p className="text-red-400 text-xs">{error}</p>}
              <button
                type="submit" disabled={loading || !email}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium transition-all disabled:opacity-40"
              >
                {loading ? <Loader2 size={15} className="animate-spin" /> : <>Send magic link <ArrowRight size={14} /></>}
              </button>
            </form>
          )}

          {/* Password form */}
          {method === 'password' && (
            <form onSubmit={handlePassword} className="space-y-3">
              {/* Register mode: name field */}
              {pwdMode === 'register' && (
                <div className="relative">
                  <User size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
                  <input
                    type="text" value={name} onChange={e => setName(e.target.value)}
                    placeholder="Your name (optional)"
                    className="w-full bg-white/5 border border-white/10 rounded-xl pl-9 pr-4 py-2.5 text-sm text-white placeholder-white/25 outline-none focus:border-purple-500/60 transition-colors"
                  />
                </div>
              )}

              <div className="relative">
                <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
                <input
                  type="email" value={email} onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com" required
                  className="w-full bg-white/5 border border-white/10 rounded-xl pl-9 pr-4 py-2.5 text-sm text-white placeholder-white/25 outline-none focus:border-purple-500/60 transition-colors"
                />
              </div>

              <div className="relative">
                <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
                <input
                  type={showPwd ? 'text' : 'password'} value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder={pwdMode === 'register' ? 'Create password (min 8 chars)' : 'Password'}
                  required
                  className="w-full bg-white/5 border border-white/10 rounded-xl pl-9 pr-10 py-2.5 text-sm text-white placeholder-white/25 outline-none focus:border-purple-500/60 transition-colors"
                />
                <button type="button" onClick={() => setShowPwd(s => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60">
                  {showPwd ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>

              {error && <p className="text-red-400 text-xs">{error}</p>}

              <button
                type="submit" disabled={loading || !email || !password}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium transition-all disabled:opacity-40"
              >
                {loading
                  ? <Loader2 size={15} className="animate-spin" />
                  : pwdMode === 'signin' ? 'Sign in' : 'Create account'}
              </button>

              <p className="text-center text-xs text-white/35">
                {pwdMode === 'signin' ? "Don't have an account? " : 'Already have an account? '}
                <button type="button"
                  onClick={() => { setPwdMode(m => m === 'signin' ? 'register' : 'signin'); setError(''); }}
                  className="text-purple-400 hover:text-purple-300 underline">
                  {pwdMode === 'signin' ? 'Create one' : 'Sign in'}
                </button>
              </p>
            </form>
          )}
        </div>

        <p className="text-center text-white/20 text-xs mt-6">
          By signing in you agree to our Terms of Service
        </p>
      </div>
    </div>
  );
}
