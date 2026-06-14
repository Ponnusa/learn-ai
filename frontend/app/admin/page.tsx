'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { CheckCircle, XCircle, Plus, Loader2, Building2, Users, KeyRound, ClipboardList } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Application {
  id: string;
  type: string;
  name: string;
  email: string;
  school_name?: string;
  subject?: string;
  inst_type?: string;
  country?: string;
  est_teachers?: number;
  est_students?: number;
  message?: string;
  created_at: string;
}

interface Invite {
  id: string;
  code: string;
  email?: string;
  note?: string;
  used_at?: string;
  expires_at: string;
  used_by_email?: string;
}

interface Stats {
  users_total: number;
  teachers_total: number;
  institutions: number;
  pending_applications: number;
  unused_invites: number;
}

export default function AdminPage() {
  const router  = useRouter();
  const { user, token } = useSessionStore();

  const [stats,    setStats]    = useState<Stats | null>(null);
  const [apps,     setApps]     = useState<Application[]>([]);
  const [invites,  setInvites]  = useState<Invite[]>([]);
  const [tab,      setTab]      = useState<'applications' | 'invites'>('applications');
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newNote,  setNewNote]  = useState('');
  const [creating, setCreating] = useState(false);

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    if (!user) { router.replace('/auth/login'); return; }
    if (user.account_type !== 'super_admin') { router.replace('/'); return; }
    loadAll();
  }, [user]);

  async function loadAll() {
    setLoading(true);
    try {
      const [sRes, aRes, iRes] = await Promise.all([
        fetch(`${API_BASE}/api/admin/stats`, { headers }),
        fetch(`${API_BASE}/api/admin/applications?status=pending`, { headers }),
        fetch(`${API_BASE}/api/admin/invites`, { headers }),
      ]);
      setStats(await sRes.json());
      setApps(await aRes.json());
      setInvites(await iRes.json());
    } catch {
      setError('Failed to load data');
    } finally {
      setLoading(false);
    }
  }

  async function review(id: string, action: 'approve' | 'reject') {
    const res = await fetch(`${API_BASE}/api/admin/applications/${id}/review`, {
      method: 'POST', headers,
      body: JSON.stringify({ action }),
    });
    const data = await res.json();
    if (!res.ok) { alert(data.detail || 'Failed'); return; }
    if (data.invite_code) alert(`Invite code generated: ${data.invite_code}`);
    loadAll();
  }

  async function createInvite(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/invites`, {
        method: 'POST', headers,
        body: JSON.stringify({ email: newEmail || undefined, note: newNote || undefined }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed');
      alert(`Invite code created: ${data.code}`);
      setNewEmail(''); setNewNote('');
      loadAll();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setCreating(false);
    }
  }

  const inputCls = `bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm text-[var(--tx1)]
                    outline-none focus:border-purple-500/60 transition-colors`;

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center">
        <Loader2 size={32} className="text-purple-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--bg)] p-6">
      <div className="max-w-4xl mx-auto">

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-[var(--tx1)] text-2xl font-bold">Super Admin</h1>
          <p className="text-[var(--tx6)] text-sm mt-1">Platform overview and teacher management</p>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-8">
            {[
              { label: 'Total users',   value: stats.users_total,          icon: Users },
              { label: 'Teachers',      value: stats.teachers_total,        icon: Users },
              { label: 'Institutions',  value: stats.institutions,          icon: Building2 },
              { label: 'Pending apps',  value: stats.pending_applications,  icon: ClipboardList },
              { label: 'Active invites', value: stats.unused_invites,       icon: KeyRound },
            ].map(s => (
              <div key={s.label} className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-4 text-center">
                <s.icon size={18} className="text-purple-400 mx-auto mb-1" />
                <p className="text-[var(--tx1)] text-xl font-bold">{s.value}</p>
                <p className="text-[var(--tx7)] text-xs mt-0.5">{s.label}</p>
              </div>
            ))}
          </div>
        )}

        {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

        {/* Tabs */}
        <div className="flex gap-1 bg-[var(--surface)] border border-[var(--bd)] rounded-xl p-1 mb-6 w-fit">
          {(['applications', 'invites'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-1.5 text-sm rounded-lg font-medium transition-all ${
                tab === t ? 'bg-purple-600 text-white' : 'text-[var(--tx6)] hover:text-[var(--tx2)]'
              }`}>
              {t === 'applications' ? `Applications (${apps.length})` : `Invite codes (${invites.filter(i => !i.used_at).length} active)`}
            </button>
          ))}
        </div>

        {/* Applications */}
        {tab === 'applications' && (
          <div className="space-y-3">
            {apps.length === 0 && (
              <p className="text-[var(--tx6)] text-sm text-center py-12">No pending applications</p>
            )}
            {apps.map(a => (
              <div key={a.id} className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        a.type === 'institution' ? 'bg-green-500/15 text-green-400' : 'bg-blue-500/15 text-blue-400'
                      }`}>
                        {a.type === 'institution' ? 'Institution' : 'Teacher'}
                      </span>
                      <span className="text-[var(--tx7)] text-xs">{new Date(a.created_at).toLocaleDateString()}</span>
                    </div>
                    <p className="text-[var(--tx1)] font-medium">{a.name}</p>
                    <p className="text-[var(--tx5)] text-sm">{a.email}</p>
                    {a.school_name && <p className="text-[var(--tx6)] text-xs mt-1">{a.school_name}{a.country ? ` · ${a.country}` : ''}</p>}
                    {a.subject && <p className="text-[var(--tx6)] text-xs">Subjects: {a.subject}</p>}
                    {a.est_teachers && <p className="text-[var(--tx6)] text-xs">~{a.est_teachers} teachers, ~{a.est_students} students</p>}
                    {a.message && <p className="text-[var(--tx7)] text-xs mt-2 italic">"{a.message}"</p>}
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button onClick={() => review(a.id, 'approve')}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-green-500/10 hover:bg-green-500/20 text-green-400 text-xs rounded-lg transition-all">
                      <CheckCircle size={13} /> Approve
                    </button>
                    <button onClick={() => review(a.id, 'reject')}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 text-xs rounded-lg transition-all">
                      <XCircle size={13} /> Reject
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Invite codes */}
        {tab === 'invites' && (
          <div className="space-y-4">
            {/* Create new invite */}
            <form onSubmit={createInvite} className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5">
              <p className="text-[var(--tx2)] text-sm font-medium mb-3">Generate invite code</p>
              <div className="flex gap-2">
                <input
                  type="email" placeholder="Email (optional — leave blank for open invite)"
                  value={newEmail} onChange={e => setNewEmail(e.target.value)}
                  className={`${inputCls} flex-1`}
                />
                <input
                  placeholder="Note (optional)"
                  value={newNote} onChange={e => setNewNote(e.target.value)}
                  className={`${inputCls} flex-1`}
                />
                <button type="submit" disabled={creating}
                  className="flex items-center gap-1.5 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl transition-all disabled:opacity-40">
                  {creating ? <Loader2 size={14} className="animate-spin" /> : <><Plus size={14} /> Create</>}
                </button>
              </div>
            </form>

            {/* Invite list */}
            <div className="space-y-2">
              {invites.map(inv => (
                <div key={inv.id} className={`flex items-center justify-between p-4 bg-[var(--surface)] border rounded-xl ${
                  inv.used_at ? 'border-[var(--bd)] opacity-50' : 'border-[var(--bd)]'
                }`}>
                  <div>
                    <div className="flex items-center gap-2">
                      <code className="text-purple-400 font-mono text-sm font-bold tracking-widest">{inv.code}</code>
                      {inv.used_at && <span className="text-xs text-[var(--tx8)]">Used by {inv.used_by_email}</span>}
                    </div>
                    {inv.email && <p className="text-[var(--tx6)] text-xs mt-0.5">For: {inv.email}</p>}
                    {inv.note  && <p className="text-[var(--tx7)] text-xs italic">{inv.note}</p>}
                  </div>
                  <span className="text-[var(--tx8)] text-xs">
                    {inv.used_at ? 'Used' : `Expires ${new Date(inv.expires_at).toLocaleDateString()}`}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
