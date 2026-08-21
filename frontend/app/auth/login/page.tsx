'use client';
import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Mail, Lock, User, Eye, EyeOff, Loader2 } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';
import { useTranslation } from '@/hooks/useTranslation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type PwdMode = 'signin' | 'register';

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setUser, sessionId } = useSessionStore();
  const { t } = useTranslation();

  const [pwdMode,  setPwdMode]  = useState<PwdMode>(searchParams.get('mode') === 'signup' ? 'register' : 'signin');
  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [name,     setName]     = useState('');
  const [showPwd,  setShowPwd]  = useState(false);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState('');

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
      const dest = data.user.account_type === 'super_admin'
        ? '/admin'
        : data.user.account_type === 'institution_admin'
          ? '/institution/dashboard'
          : data.user.account_type === 'teacher'
            ? '/teacher/dashboard'
            : '/';
      router.replace(dest);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center p-4">
      <div className="w-full max-w-sm">

        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 mx-auto mb-4">
            <img src="/logo-64.png" alt="Learn-AI" className="w-full h-full object-contain drop-shadow-xl" />
          </div>
          <h1 className="text-[var(--tx1)] text-xl font-bold">{t.auth.signInToApp}</h1>
          <p className="text-[var(--tx6)] text-sm mt-1">{t.auth.continueJourney}</p>
        </div>

        {/* Card */}
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-6 shadow-xl shadow-black/10">

          {/* Password form */}
          <form onSubmit={handlePassword} className="space-y-3">
              {pwdMode === 'register' && (
                <div className="relative">
                  <User size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--tx8)]" />
                  <input
                    type="text" value={name} onChange={e => setName(e.target.value)}
                    placeholder={t.auth.yourNamePlaceholder}
                    className="w-full bg-[var(--ov1)] border border-[var(--bd)] rounded-xl pl-9 pr-4 py-2.5
                               text-sm text-[var(--tx1)] t-ph outline-none focus:border-purple-500/60 transition-colors"
                  />
                </div>
              )}

              <div className="relative">
                <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--tx8)]" />
                <input
                  type="email" value={email} onChange={e => setEmail(e.target.value)}
                  placeholder={t.auth.emailPlaceholder} required
                  className="w-full bg-[var(--ov1)] border border-[var(--bd)] rounded-xl pl-9 pr-4 py-2.5
                             text-sm text-[var(--tx1)] t-ph outline-none focus:border-purple-500/60 transition-colors"
                />
              </div>

              <div className="relative">
                <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--tx8)]" />
                <input
                  type={showPwd ? 'text' : 'password'} value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder={pwdMode === 'register' ? t.auth.createPasswordPlaceholder : t.auth.passwordPlaceholder}
                  required
                  className="w-full bg-[var(--ov1)] border border-[var(--bd)] rounded-xl pl-9 pr-10 py-2.5
                             text-sm text-[var(--tx1)] t-ph outline-none focus:border-purple-500/60 transition-colors"
                />
                <button type="button" onClick={() => setShowPwd(s => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--tx8)] hover:text-[var(--tx3)]">
                  {showPwd ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>

              {error && <p className="text-[var(--red)] text-xs">{error}</p>}

              <button
                type="submit" disabled={loading || !email || !password}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl
                           bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium transition-all disabled:opacity-40"
              >
                {loading
                  ? <Loader2 size={15} className="animate-spin" />
                  : pwdMode === 'signin' ? t.auth.signInBtn : t.auth.createAccountBtn}
              </button>

              <p className="text-center text-xs text-[var(--tx7)]">
                {pwdMode === 'signin' ? `${t.auth.dontHaveAccount} ` : `${t.auth.alreadyAccountQuestion} `}
                <button type="button"
                  onClick={() => { setPwdMode(m => m === 'signin' ? 'register' : 'signin'); setError(''); }}
                  className="text-[var(--purple)] hover:underline">
                  {pwdMode === 'signin' ? t.auth.createOne : t.auth.signIn}
                </button>
              </p>
            </form>
        </div>

        <p className="text-center text-[var(--txa)] text-xs mt-6">
          {t.auth.termsNote}
        </p>

        <div className="flex items-center justify-center gap-4 mt-4 text-xs">
          <a href="/join" className="text-purple-400 hover:text-purple-300 font-medium transition-colors">
            Student? Join with class code →
          </a>
          <a href="/auth/teacher" className="text-[var(--tx7)] hover:text-[var(--purple)] transition-colors">
            For teachers →
          </a>
        </div>
      </div>
    </div>
  );
}
