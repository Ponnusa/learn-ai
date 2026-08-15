'use client';
import { useEffect, useState } from 'react';
import { GraduationCap, Loader2, UserPlus, Trash2, Copy, Check, Link2, Eye, EyeOff } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Teacher { id: string; name: string; email: string; }
interface Invite  { token: string; email: string | null; status: string; expires_at: string; }
interface Created { email: string; temp_password: string; note: string; }

export default function TeachersPage() {
  const { token } = useSessionStore();
  const [teachers,  setTeachers]  = useState<Teacher[]>([]);
  const [invites,   setInvites]   = useState<Invite[]>([]);
  const [loading,   setLoading]   = useState(true);
  const [tab,       setTab]       = useState<'create' | 'invite'>('create');

  // Create-account form
  const [form,      setForm]      = useState({ name: '', email: '', password: '' });
  const [showPwd,   setShowPwd]   = useState(false);
  const [creating,  setCreating]  = useState(false);
  const [created,   setCreated]   = useState<Created | null>(null);

  // Invite-link form
  const [invEmail,  setInvEmail]  = useState('');
  const [sending,   setSending]   = useState(false);
  const [copied,    setCopied]    = useState<string | null>(null);

  async function load() {
    const [tRes, iRes] = await Promise.all([
      fetch(`${API}/api/school/teachers`, { headers: { Authorization: `Bearer ${token}` } }),
      fetch(`${API}/api/school/invites`,  { headers: { Authorization: `Bearer ${token}` } }),
    ]);
    if (tRes.ok) setTeachers(await tRes.json());
    if (iRes.ok) setInvites(await iRes.json());
    setLoading(false);
  }

  useEffect(() => { if (token) load(); }, [token]);

  async function createAccount() {
    if (!form.name.trim() || !form.email.trim()) return;
    setCreating(true);
    setCreated(null);
    try {
      const res = await fetch(`${API}/api/school/teachers/create`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name.trim(),
          email: form.email.trim(),
          password: form.password.trim() || null,
        }),
      });
      if (res.ok) {
        const d = await res.json();
        setCreated(d);
        setForm({ name: '', email: '', password: '' });
        await load();
      }
    } finally { setCreating(false); }
  }

  async function sendInvite() {
    if (!invEmail.trim() && invEmail !== '') return;
    setSending(true);
    try {
      const res = await fetch(`${API}/api/school/invites`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: invEmail.trim() || null, role: 'teacher' }),
      });
      if (res.ok) { setInvEmail(''); await load(); }
    } finally { setSending(false); }
  }

  function copyLink(tok: string) {
    const url = `${window.location.origin}/auth/school-invite?token=${tok}`;
    navigator.clipboard.writeText(url).then(() => {
      setCopied(tok); setTimeout(() => setCopied(null), 2000);
    });
  }

  function copyText(text: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(text); setTimeout(() => setCopied(null), 2000);
    });
  }

  async function removeTeacher(id: string) {
    if (!confirm('Remove this teacher from the school?')) return;
    await fetch(`${API}/api/school/teachers/${id}`, {
      method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
    });
    await load();
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h1 className="text-[var(--tx1)] text-xl font-bold mb-6">Teachers</h1>

      {/* Tab switcher */}
      <div className="flex gap-1 p-1 bg-[var(--ov2)] rounded-xl mb-5 w-fit">
        {(['create', 'invite'] as const).map(t => (
          <button
            key={t}
            onClick={() => { setTab(t); setCreated(null); }}
            className={`px-4 py-1.5 text-sm rounded-lg transition-colors ${
              tab === t
                ? 'bg-[var(--surface)] text-[var(--tx1)] shadow-sm'
                : 'text-[var(--tx6)] hover:text-[var(--tx3)]'
            }`}
          >
            {t === 'create' ? (
              <span className="flex items-center gap-1.5"><UserPlus size={14} /> Create Login</span>
            ) : (
              <span className="flex items-center gap-1.5"><Link2 size={14} /> Invite Link</span>
            )}
          </button>
        ))}
      </div>

      {/* Create account */}
      {tab === 'create' && (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-6">
          <p className="text-[var(--tx3)] text-sm font-medium mb-4">
            Create teacher account — teacher can log in immediately with email + password.
          </p>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label className="block text-xs text-[var(--tx6)] mb-1">Full Name *</label>
              <input
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="Teacher name"
                className="w-full bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                           text-[var(--tx1)] placeholder:text-[var(--tx7)] outline-none focus:border-purple-500/60"
              />
            </div>
            <div>
              <label className="block text-xs text-[var(--tx6)] mb-1">Email *</label>
              <input
                value={form.email}
                onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                placeholder="teacher@email.com"
                type="email"
                className="w-full bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                           text-[var(--tx1)] placeholder:text-[var(--tx7)] outline-none focus:border-purple-500/60"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-[var(--tx6)] mb-1">
                Password <span className="text-[var(--tx7)]">(leave blank to auto-generate)</span>
              </label>
              <div className="relative">
                <input
                  value={form.password}
                  onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                  placeholder="Auto-generate"
                  type={showPwd ? 'text' : 'password'}
                  className="w-full bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 pr-10 text-sm
                             text-[var(--tx1)] placeholder:text-[var(--tx7)] outline-none focus:border-purple-500/60"
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--tx7)] hover:text-[var(--tx3)]"
                >
                  {showPwd ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>
          </div>
          <button
            onClick={createAccount}
            disabled={creating || !form.name.trim() || !form.email.trim()}
            className="px-5 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl
                       transition-colors disabled:opacity-40"
          >
            {creating ? <Loader2 size={14} className="animate-spin" /> : 'Create Account'}
          </button>

          {/* Success panel */}
          {created && (
            <div className="mt-4 p-4 rounded-xl bg-green-500/10 border border-green-500/30">
              <p className="text-green-400 text-sm font-semibold mb-2">Account created!</p>
              <div className="space-y-1.5 text-sm">
                {[
                  { label: 'Email', val: created.email },
                  { label: 'Password', val: created.temp_password },
                ].map(r => (
                  <div key={r.label} className="flex items-center justify-between">
                    <span className="text-[var(--tx6)] text-xs w-20">{r.label}</span>
                    <span className="font-mono text-[var(--tx2)] flex-1">{r.val}</span>
                    <button
                      onClick={() => copyText(r.val)}
                      className="ml-2 text-[var(--tx7)] hover:text-[var(--tx2)] transition-colors"
                    >
                      {copied === r.val ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
                    </button>
                  </div>
                ))}
              </div>
              <p className="text-[var(--tx7)] text-xs mt-2">{created.note}</p>
            </div>
          )}
        </div>
      )}

      {/* Invite link */}
      {tab === 'invite' && (
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-6">
          <p className="text-[var(--tx3)] text-sm font-medium mb-1">Generate an invite link</p>
          <p className="text-[var(--tx7)] text-xs mb-4">
            Teacher clicks the link, signs up/in, and is automatically added to this school. Leave email blank for an open link.
          </p>
          <div className="flex gap-2">
            <input
              value={invEmail}
              onChange={e => setInvEmail(e.target.value)}
              placeholder="teacher@email.com  (optional — locks link to one person)"
              className="flex-1 bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                         text-[var(--tx1)] placeholder:text-[var(--tx7)] outline-none focus:border-purple-500/60"
            />
            <button
              onClick={sendInvite}
              disabled={sending}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl
                         transition-colors disabled:opacity-40"
            >
              {sending ? <Loader2 size={14} className="animate-spin" /> : 'Generate'}
            </button>
          </div>
          {invites.filter(i => i.status === 'pending').length > 0 && (
            <div className="mt-4 flex flex-col gap-2">
              {invites.filter(i => i.status === 'pending').map(inv => (
                <div key={inv.token}
                  className="flex items-center justify-between bg-[var(--ov2)] rounded-xl px-4 py-3">
                  <div>
                    <p className="text-[var(--tx2)] text-sm">{inv.email ?? 'Open invite'}</p>
                    <p className="text-[var(--tx7)] text-xs">
                      Expires {new Date(inv.expires_at).toLocaleDateString()}
                    </p>
                  </div>
                  <button
                    onClick={() => copyLink(inv.token)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg
                               bg-[var(--surface)] text-[var(--tx5)] hover:text-[var(--tx1)] transition-colors"
                  >
                    {copied === inv.token
                      ? <><Check size={12} className="text-green-400" /> Copied</>
                      : <><Copy size={12} /> Copy link</>
                    }
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Teacher list */}
      <h2 className="text-[var(--tx3)] text-sm font-semibold mb-3">
        Active Teachers ({teachers.length})
      </h2>
      {teachers.length === 0 ? (
        <p className="text-[var(--tx7)] text-sm">No teachers yet.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {teachers.map(t => (
            <div key={t.id}
              className="flex items-center justify-between bg-[var(--surface)] border border-[var(--bd)]
                         rounded-xl px-4 py-3">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-purple-600/20 flex items-center justify-center shrink-0">
                  <GraduationCap size={15} className="text-purple-400" />
                </div>
                <div>
                  <p className="text-[var(--tx1)] text-sm font-medium">{t.name}</p>
                  <p className="text-[var(--tx7)] text-xs">{t.email}</p>
                </div>
              </div>
              <button
                onClick={() => removeTeacher(t.id)}
                className="p-2 text-[var(--tx7)] hover:text-red-400 transition-colors"
                title="Remove from school"
              >
                <Trash2 size={15} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
