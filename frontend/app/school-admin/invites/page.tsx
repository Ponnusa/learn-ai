'use client';
import { useEffect, useState } from 'react';
import { Mail, Loader2, Copy, Check } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Invite {
  token: string; email: string | null; role: string;
  status: 'pending' | 'used' | 'expired'; accepted_by: string | null; expires_at: string;
}

export default function InvitesPage() {
  const { token } = useSessionStore();
  const [invites,  setInvites]  = useState<Invite[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [email,    setEmail]    = useState('');
  const [role,     setRole]     = useState('teacher');
  const [sending,  setSending]  = useState(false);
  const [copied,   setCopied]   = useState<string | null>(null);

  async function load() {
    const res = await fetch(`${API}/api/school/invites`, { headers: { Authorization: `Bearer ${token}` } });
    if (res.ok) setInvites(await res.json());
    setLoading(false);
  }

  useEffect(() => { if (token) load(); }, [token]);

  async function create() {
    setSending(true);
    try {
      const res = await fetch(`${API}/api/school/invites`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim() || null, role }),
      });
      if (res.ok) { setEmail(''); await load(); }
    } finally { setSending(false); }
  }

  function copy(tok: string) {
    const url = `${window.location.origin}/auth/school-invite?token=${tok}`;
    navigator.clipboard.writeText(url).then(() => {
      setCopied(tok);
      setTimeout(() => setCopied(null), 2000);
    });
  }

  const statusColor = (s: string) =>
    s === 'pending' ? 'text-green-400 bg-green-500/10' :
    s === 'used'    ? 'text-[var(--tx7)] bg-[var(--ov2)]' :
                      'text-red-400 bg-red-500/10';

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h1 className="text-[var(--tx1)] text-xl font-bold mb-6">Invites</h1>

      {/* Create invite */}
      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-6">
        <p className="text-[var(--tx3)] text-sm font-medium mb-3 flex items-center gap-2">
          <Mail size={15} className="text-purple-400" /> Create Invite Link
        </p>
        <div className="flex gap-2 mb-2">
          <input
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="Email (leave blank for open link)"
            className="flex-1 bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                       text-[var(--tx1)] placeholder:text-[var(--tx7)] outline-none focus:border-purple-500/60"
          />
          <select
            value={role}
            onChange={e => setRole(e.target.value)}
            className="bg-[var(--ov2)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                       text-[var(--tx1)] outline-none focus:border-purple-500/60"
          >
            <option value="teacher">Teacher</option>
          </select>
          <button onClick={create} disabled={sending}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl disabled:opacity-40">
            {sending ? <Loader2 size={14} className="animate-spin" /> : 'Create'}
          </button>
        </div>
        <p className="text-xs text-[var(--tx7)]">
          Links are valid for 7 days. Share the link with the teacher — they click it to join the school.
        </p>
      </div>

      {/* Invite list */}
      {invites.length === 0 ? (
        <p className="text-[var(--tx7)] text-sm">No invites yet.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {invites.map(inv => (
            <div key={inv.token}
              className="bg-[var(--surface)] border border-[var(--bd)] rounded-xl px-4 py-3
                         flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[var(--tx2)] text-sm truncate">
                  {inv.email ?? <span className="text-[var(--tx6)] italic">Open link</span>}
                </p>
                <p className="text-[var(--tx7)] text-xs mt-0.5">
                  Expires {new Date(inv.expires_at).toLocaleDateString()}
                  {inv.accepted_by && ` · Accepted by ${inv.accepted_by}`}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className={`text-xs px-2 py-0.5 rounded-full ${statusColor(inv.status)}`}>
                  {inv.status}
                </span>
                {inv.status === 'pending' && (
                  <button onClick={() => copy(inv.token)}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg
                               bg-[var(--ov2)] text-[var(--tx5)] hover:text-[var(--tx1)] transition-colors">
                    {copied === inv.token
                      ? <><Check size={12} className="text-green-400" /> Copied</>
                      : <><Copy size={12} /> Copy</>
                    }
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
