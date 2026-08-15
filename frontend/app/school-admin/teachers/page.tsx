'use client';
import { useEffect, useState } from 'react';
import { GraduationCap, Loader2, UserPlus, Trash2, Copy, Check } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Teacher { id: string; name: string; email: string; }
interface Invite  { token: string; email: string | null; status: string; expires_at: string; }

export default function TeachersPage() {
  const { token } = useSessionStore();
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [invites,  setInvites]  = useState<Invite[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [invEmail, setInvEmail] = useState('');
  const [sending,  setSending]  = useState(false);
  const [copied,   setCopied]   = useState<string | null>(null);

  async function load() {
    const [tRes, iRes] = await Promise.all([
      fetch(`${API}/api/school/teachers`,   { headers: { Authorization: `Bearer ${token}` } }),
      fetch(`${API}/api/school/invites`,     { headers: { Authorization: `Bearer ${token}` } }),
    ]);
    if (tRes.ok) setTeachers(await tRes.json());
    if (iRes.ok) setInvites(await iRes.json());
    setLoading(false);
  }

  useEffect(() => { if (token) load(); }, [token]);

  async function sendInvite() {
    if (!invEmail.trim()) return;
    setSending(true);
    try {
      const res = await fetch(`${API}/api/school/invites`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: invEmail.trim(), role: 'teacher' }),
      });
      if (res.ok) { setInvEmail(''); await load(); }
    } finally { setSending(false); }
  }

  function copyLink(tok: string) {
    const url = `${window.location.origin}/auth/school-invite?token=${tok}`;
    navigator.clipboard.writeText(url).then(() => {
      setCopied(tok);
      setTimeout(() => setCopied(null), 2000);
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

      {/* Invite form */}
      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-6">
        <p className="text-[var(--tx3)] text-sm font-medium mb-3 flex items-center gap-2">
          <UserPlus size={16} className="text-purple-400" /> Invite a Teacher
        </p>
        <div className="flex gap-2">
          <input
            value={invEmail}
            onChange={e => setInvEmail(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && sendInvite()}
            placeholder="teacher@email.com  (leave blank for open link)"
            className="flex-1 bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                       text-[var(--tx1)] placeholder:text-[var(--tx7)] outline-none
                       focus:border-purple-500/60 transition-colors"
          />
          <button
            onClick={sendInvite}
            disabled={sending}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl
                       transition-colors disabled:opacity-40"
          >
            {sending ? <Loader2 size={14} className="animate-spin" /> : 'Send'}
          </button>
        </div>
      </div>

      {/* Teacher list */}
      <div className="mb-6">
        <h2 className="text-[var(--tx3)] text-sm font-semibold mb-3">
          Active Teachers ({teachers.length})
        </h2>
        {teachers.length === 0 ? (
          <p className="text-[var(--tx7)] text-sm">No teachers yet. Send an invite above.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {teachers.map(t => (
              <div
                key={t.id}
                className="flex items-center justify-between bg-[var(--surface)] border border-[var(--bd)]
                           rounded-xl px-4 py-3"
              >
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
                  className="text-[var(--tx7)] hover:text-red-400 transition-colors p-1.5"
                  title="Remove from school"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pending invites */}
      {invites.filter(i => i.status === 'pending').length > 0 && (
        <div>
          <h2 className="text-[var(--tx3)] text-sm font-semibold mb-3">Pending Invites</h2>
          <div className="flex flex-col gap-2">
            {invites.filter(i => i.status === 'pending').map(inv => (
              <div
                key={inv.token}
                className="flex items-center justify-between bg-[var(--surface)] border border-[var(--bd)]
                           rounded-xl px-4 py-3"
              >
                <div>
                  <p className="text-[var(--tx2)] text-sm">{inv.email ?? 'Open invite link'}</p>
                  <p className="text-[var(--tx7)] text-xs">
                    Expires {new Date(inv.expires_at).toLocaleDateString()}
                  </p>
                </div>
                <button
                  onClick={() => copyLink(inv.token)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg
                             bg-[var(--ov2)] text-[var(--tx4)] hover:text-[var(--tx1)] transition-colors"
                >
                  {copied === inv.token ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
                  {copied === inv.token ? 'Copied!' : 'Copy link'}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
