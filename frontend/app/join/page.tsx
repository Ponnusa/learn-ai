'use client';
import { useState, useRef, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { KeyRound, User, Lock, Eye, EyeOff, Loader2, CheckCircle2, ArrowRight } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function JoinPage() {
  const router       = useRouter();
  const params       = useSearchParams();
  const { setUser }  = useSessionStore();

  const [step,       setStep]      = useState<'code' | 'details'>('code');
  const [code,       setCode]      = useState(params.get('code') || '');
  const [classroom,  setClassroom] = useState<{ id: string; name: string } | null>(null);
  const [name,       setName]      = useState('');
  const [password,   setPassword]  = useState('');
  const [showPwd,    setShowPwd]   = useState(false);
  const [loading,    setLoading]   = useState(false);
  const [error,      setError]     = useState('');

  const codeRef = useRef<HTMLInputElement>(null);
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Auto-advance if code is pre-filled from URL
    if (params.get('code') && params.get('code')!.length === 6) {
      validateCode(params.get('code')!.toUpperCase());
    } else {
      codeRef.current?.focus();
    }
  }, []);

  useEffect(() => {
    if (step === 'details') nameRef.current?.focus();
  }, [step]);

  async function validateCode(raw = code) {
    const c = raw.trim().toUpperCase();
    if (c.length !== 6) { setError('Enter the 6-character class code from your teacher'); return; }
    setLoading(true); setError('');
    try {
      // Ping the backend to validate the code before asking for name/password
      const res  = await fetch(`${API_BASE}/api/classrooms/by-code/${c}`);
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || 'Class code not found — check with your teacher');
      }
      const cls = await res.json();
      setClassroom(cls);
      setCode(c);
      setStep('details');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleJoin(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !password || loading) return;
    setLoading(true); setError('');
    try {
      const res  = await fetch(`${API_BASE}/api/auth/student-join`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ join_code: code, name: name.trim(), password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not join class');
      setUser(data.user, data.token);
      router.replace(`/classrooms/${data.classroom.id}`);
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
            <img src="/logo-64.png" alt="LearnX-AI" className="w-full h-full object-contain drop-shadow-xl" />
          </div>
          <h1 className="text-[var(--tx1)] text-xl font-bold">Join your class</h1>
          <p className="text-[var(--tx6)] text-sm mt-1">Enter the code your teacher gave you</p>
        </div>

        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-6 shadow-xl shadow-black/10">

          {/* Step 1 — class code */}
          {step === 'code' && (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-[var(--tx6)] mb-1.5">Class code</label>
                <div className="relative">
                  <KeyRound size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--tx8)]" />
                  <input
                    ref={codeRef}
                    type="text"
                    value={code}
                    onChange={e => { setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '')); setError(''); }}
                    onKeyDown={e => e.key === 'Enter' && validateCode()}
                    maxLength={6}
                    placeholder="ABC123"
                    className="w-full bg-[var(--ov1)] border border-[var(--bd)] rounded-xl pl-9 pr-4 py-3
                               text-lg font-mono font-bold text-center tracking-[0.35em] text-[var(--tx1)]
                               outline-none focus:border-purple-500/60 transition-colors uppercase"
                  />
                </div>
              </div>

              {error && <p className="text-red-400 text-xs">{error}</p>}

              <button
                onClick={() => validateCode()}
                disabled={code.length !== 6 || loading}
                className="w-full flex items-center justify-center gap-2 py-3 rounded-xl
                           bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium
                           transition-all disabled:opacity-40">
                {loading
                  ? <Loader2 size={15} className="animate-spin" />
                  : <><span>Continue</span><ArrowRight size={14} /></>}
              </button>
            </div>
          )}

          {/* Step 2 — name + password */}
          {step === 'details' && classroom && (
            <form onSubmit={handleJoin} className="space-y-4">
              {/* Classroom confirmed */}
              <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-green-500/10 border border-green-500/20">
                <CheckCircle2 size={14} className="text-green-400 shrink-0" />
                <div className="min-w-0">
                  <p className="text-green-400 text-xs font-medium truncate">{classroom.name}</p>
                  <button type="button" onClick={() => { setStep('code'); setError(''); }}
                    className="text-[var(--tx8)] text-xs hover:text-[var(--tx5)] transition-colors">
                    Wrong class? Change code
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-[var(--tx6)] mb-1.5">Your name</label>
                <div className="relative">
                  <User size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--tx8)]" />
                  <input
                    ref={nameRef}
                    type="text"
                    value={name}
                    onChange={e => { setName(e.target.value); setError(''); }}
                    placeholder="First name"
                    maxLength={50}
                    required
                    className="w-full bg-[var(--ov1)] border border-[var(--bd)] rounded-xl pl-9 pr-4 py-2.5
                               text-sm text-[var(--tx1)] outline-none focus:border-purple-500/60 transition-colors"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-[var(--tx6)] mb-1.5">Create a password</label>
                <div className="relative">
                  <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--tx8)]" />
                  <input
                    type={showPwd ? 'text' : 'password'}
                    value={password}
                    onChange={e => { setPassword(e.target.value); setError(''); }}
                    placeholder="Min. 6 characters"
                    minLength={6}
                    required
                    className="w-full bg-[var(--ov1)] border border-[var(--bd)] rounded-xl pl-9 pr-10 py-2.5
                               text-sm text-[var(--tx1)] outline-none focus:border-purple-500/60 transition-colors"
                  />
                  <button type="button" onClick={() => setShowPwd(s => !s)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--tx8)] hover:text-[var(--tx3)]">
                    {showPwd ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
                <p className="text-[var(--tx8)] text-xs mt-1">Remember this — you&apos;ll need it to sign in next time</p>
              </div>

              {error && <p className="text-red-400 text-xs">{error}</p>}

              <button
                type="submit"
                disabled={!name.trim() || password.length < 6 || loading}
                className="w-full flex items-center justify-center gap-2 py-3 rounded-xl
                           bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium
                           transition-all disabled:opacity-40">
                {loading ? <Loader2 size={15} className="animate-spin" /> : 'Join class'}
              </button>
            </form>
          )}
        </div>

        <p className="text-center text-xs mt-6 text-[var(--tx7)]">
          Already have an account?{' '}
          <a href="/auth/login" className="text-[var(--purple)] hover:underline">Sign in</a>
        </p>
      </div>
    </div>
  );
}
