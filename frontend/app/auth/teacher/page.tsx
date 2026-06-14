'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { GraduationCap, Building2, KeyRound, ArrowRight, Loader2, CheckCircle } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type View = 'hub' | 'apply' | 'institution' | 'invite';

export default function TeacherAuthPage() {
  const router = useRouter();
  const [view,    setView]    = useState<View>('hub');
  const [loading, setLoading] = useState(false);
  const [done,    setDone]    = useState('');
  const [error,   setError]   = useState('');

  // Standalone teacher application
  const [tName,   setTName]   = useState('');
  const [tEmail,  setTEmail]  = useState('');
  const [tSchool, setTSchool] = useState('');
  const [tSubj,   setTSubj]   = useState('');
  const [tMsg,    setTMsg]    = useState('');

  // Institution application
  const [iName,    setIName]    = useState('');
  const [iEmail,   setIEmail]   = useState('');
  const [iSchool,  setISchool]  = useState('');
  const [iType,    setIType]    = useState('school');
  const [iCountry, setICountry] = useState('');
  const [iDomain,  setIDomain]  = useState('');
  const [iTchr,    setITchr]    = useState('');
  const [iStud,    setIStud]    = useState('');
  const [iMsg,     setIMsg]     = useState('');

  async function submitTeacher(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const res = await fetch(`${API_BASE}/api/teacher-auth/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: tName, email: tEmail, school_name: tSchool, subject: tSubj, message: tMsg }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Submission failed');
      setDone(data.message);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function submitInstitution(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const res = await fetch(`${API_BASE}/api/teacher-auth/apply-institution`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: iName, email: iEmail, school_name: iSchool,
          inst_type: iType, country: iCountry, email_domain: iDomain,
          est_teachers: iTchr ? parseInt(iTchr) : undefined,
          est_students: iStud ? parseInt(iStud) : undefined,
          message: iMsg,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Submission failed');
      setDone(data.message);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const inputCls = `w-full bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-4 py-2.5
                    text-sm text-[var(--tx1)] outline-none focus:border-purple-500/60 transition-colors`;

  // ── Success state ──────────────────────────────────────────────────────────
  if (done) {
    return (
      <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center p-4">
        <div className="text-center max-w-sm">
          <CheckCircle size={48} className="text-green-400 mx-auto mb-4" />
          <p className="text-[var(--tx1)] text-lg font-semibold mb-2">Application received</p>
          <p className="text-[var(--tx5)] text-sm mb-6">{done}</p>
          <button onClick={() => router.push('/')} className="text-[var(--purple)] hover:underline text-sm">
            Back to home
          </button>
        </div>
      </div>
    );
  }

  // ── Hub view ───────────────────────────────────────────────────────────────
  if (view === 'hub') {
    return (
      <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center p-4">
        <div className="w-full max-w-sm">
          <div className="text-center mb-8">
            <GraduationCap size={40} className="text-purple-400 mx-auto mb-3" />
            <h1 className="text-[var(--tx1)] text-xl font-bold">Educators &amp; Schools</h1>
            <p className="text-[var(--tx6)] text-sm mt-1">Choose how you want to get started</p>
          </div>

          <div className="space-y-3">
            <button
              onClick={() => setView('invite')}
              className="w-full flex items-center gap-4 p-4 bg-[var(--surface)] border border-[var(--bd)]
                         hover:border-purple-500/40 rounded-2xl text-left transition-all group"
            >
              <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center shrink-0">
                <KeyRound size={18} className="text-purple-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[var(--tx1)] text-sm font-medium">I have an invite code</p>
                <p className="text-[var(--tx7)] text-xs mt-0.5">Redeem your code and get instant access</p>
              </div>
              <ArrowRight size={15} className="text-[var(--tx8)] group-hover:text-purple-400 transition-colors" />
            </button>

            <button
              onClick={() => setView('apply')}
              className="w-full flex items-center gap-4 p-4 bg-[var(--surface)] border border-[var(--bd)]
                         hover:border-purple-500/40 rounded-2xl text-left transition-all group"
            >
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center shrink-0">
                <GraduationCap size={18} className="text-blue-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[var(--tx1)] text-sm font-medium">Apply as a teacher</p>
                <p className="text-[var(--tx7)] text-xs mt-0.5">Individual teacher — we'll review and get back to you</p>
              </div>
              <ArrowRight size={15} className="text-[var(--tx8)] group-hover:text-purple-400 transition-colors" />
            </button>

            <button
              onClick={() => setView('institution')}
              className="w-full flex items-center gap-4 p-4 bg-[var(--surface)] border border-[var(--bd)]
                         hover:border-purple-500/40 rounded-2xl text-left transition-all group"
            >
              <div className="w-10 h-10 rounded-xl bg-green-500/10 flex items-center justify-center shrink-0">
                <Building2 size={18} className="text-green-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[var(--tx1)] text-sm font-medium">Register my school / institution</p>
                <p className="text-[var(--tx7)] text-xs mt-0.5">Onboard your whole team of teachers and students</p>
              </div>
              <ArrowRight size={15} className="text-[var(--tx8)] group-hover:text-purple-400 transition-colors" />
            </button>
          </div>

          <p className="text-center mt-6">
            <button onClick={() => router.push('/auth/login')} className="text-[var(--tx7)] hover:text-[var(--purple)] text-xs transition-colors">
              ← Back to student login
            </button>
          </p>
        </div>
      </div>
    );
  }

  // ── Invite code redemption ─────────────────────────────────────────────────
  if (view === 'invite') {
    return (
      <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center p-4">
        <div className="w-full max-w-sm">
          <button onClick={() => setView('hub')} className="text-[var(--tx7)] hover:text-[var(--purple)] text-xs mb-6 transition-colors">
            ← Back
          </button>
          <h2 className="text-[var(--tx1)] text-lg font-bold mb-1">Redeem invite code</h2>
          <p className="text-[var(--tx6)] text-sm mb-6">Enter the code you received from your admin or our team</p>

          <form onSubmit={async (e) => {
            e.preventDefault();
            const fd = new FormData(e.currentTarget);
            setLoading(true); setError('');
            try {
              const res = await fetch(`${API_BASE}/api/teacher-auth/redeem-invite`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  code:  fd.get('code'),
                  name:  fd.get('name'),
                  email: fd.get('email'),
                }),
              });
              const data = await res.json();
              if (!res.ok) throw new Error(data.detail || 'Redemption failed');
              // Auto-verify the token
              if (data.verify_token) {
                router.replace(`/auth/verify?token=${data.verify_token}`);
              } else {
                setDone('Invite redeemed — check your email to sign in.');
              }
            } catch (err: any) {
              setError(err.message);
            } finally {
              setLoading(false);
            }
          }} className="space-y-3">
            <input name="code" required placeholder="Invite code (e.g. AB12CD34)" className={inputCls} />
            <input name="name" required placeholder="Your full name" className={inputCls} />
            <input name="email" type="email" required placeholder="Your email address" className={inputCls} />
            {error && <p className="text-red-400 text-xs">{error}</p>}
            <button
              type="submit" disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl
                         bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium transition-all disabled:opacity-40"
            >
              {loading ? <Loader2 size={15} className="animate-spin" /> : <>Redeem &amp; sign in <ArrowRight size={14} /></>}
            </button>
          </form>
        </div>
      </div>
    );
  }

  // ── Standalone teacher application ────────────────────────────────────────
  if (view === 'apply') {
    return (
      <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center p-4">
        <div className="w-full max-w-sm">
          <button onClick={() => setView('hub')} className="text-[var(--tx7)] hover:text-[var(--purple)] text-xs mb-6 transition-colors">
            ← Back
          </button>
          <h2 className="text-[var(--tx1)] text-lg font-bold mb-1">Apply as a teacher</h2>
          <p className="text-[var(--tx6)] text-sm mb-6">We'll review your application and send an invite within 24 hours</p>

          <form onSubmit={submitTeacher} className="space-y-3">
            <input required placeholder="Your full name" value={tName} onChange={e => setTName(e.target.value)} className={inputCls} />
            <input required type="email" placeholder="Your email address" value={tEmail} onChange={e => setTEmail(e.target.value)} className={inputCls} />
            <input placeholder="School / institution (optional)" value={tSchool} onChange={e => setTSchool(e.target.value)} className={inputCls} />
            <input placeholder="Subjects you teach (optional)" value={tSubj} onChange={e => setTSubj(e.target.value)} className={inputCls} />
            <textarea
              placeholder="Anything else you'd like to share? (optional)"
              value={tMsg} onChange={e => setTMsg(e.target.value)} rows={3}
              className={`${inputCls} resize-none`}
            />
            {error && <p className="text-red-400 text-xs">{error}</p>}
            <button
              type="submit" disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl
                         bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium transition-all disabled:opacity-40"
            >
              {loading ? <Loader2 size={15} className="animate-spin" /> : <>Submit application <ArrowRight size={14} /></>}
            </button>
          </form>
        </div>
      </div>
    );
  }

  // ── Institution application ────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <button onClick={() => setView('hub')} className="text-[var(--tx7)] hover:text-[var(--purple)] text-xs mb-6 transition-colors">
          ← Back
        </button>
        <h2 className="text-[var(--tx1)] text-lg font-bold mb-1">Register your institution</h2>
        <p className="text-[var(--tx6)] text-sm mb-6">We'll set up your school's workspace within 24 hours</p>

        <form onSubmit={submitInstitution} className="space-y-3">
          <input required placeholder="Your name (admin contact)" value={iName} onChange={e => setIName(e.target.value)} className={inputCls} />
          <input required type="email" placeholder="Your email address" value={iEmail} onChange={e => setIEmail(e.target.value)} className={inputCls} />
          <input required placeholder="School / institution name" value={iSchool} onChange={e => setISchool(e.target.value)} className={inputCls} />
          <select value={iType} onChange={e => setIType(e.target.value)} className={inputCls}>
            <option value="school">School</option>
            <option value="tuition_center">Tuition center</option>
            <option value="university">University</option>
            <option value="coaching">Coaching institute</option>
          </select>
          <input placeholder="Country" value={iCountry} onChange={e => setICountry(e.target.value)} className={inputCls} />
          <input placeholder="School email domain (e.g. school.edu)" value={iDomain} onChange={e => setIDomain(e.target.value)} className={inputCls} />
          <div className="flex gap-2">
            <input type="number" placeholder="Est. teachers" value={iTchr} onChange={e => setITchr(e.target.value)} className={inputCls} />
            <input type="number" placeholder="Est. students" value={iStud} onChange={e => setIStud(e.target.value)} className={inputCls} />
          </div>
          <textarea
            placeholder="Anything else? (optional)"
            value={iMsg} onChange={e => setIMsg(e.target.value)} rows={3}
            className={`${inputCls} resize-none`}
          />
          {error && <p className="text-red-400 text-xs">{error}</p>}
          <button
            type="submit" disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl
                       bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium transition-all disabled:opacity-40"
          >
            {loading ? <Loader2 size={15} className="animate-spin" /> : <>Submit application <ArrowRight size={14} /></>}
          </button>
        </form>
      </div>
    </div>
  );
}
