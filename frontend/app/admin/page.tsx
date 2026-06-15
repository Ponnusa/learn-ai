'use client';
import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  CheckCircle, XCircle, Plus, Loader2, Building2, Users,
  KeyRound, ClipboardList, MessageSquare, Video, Search,
  ToggleLeft, ToggleRight, Copy, Check, KeySquare,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type Tab = 'users' | 'applications' | 'invites';

interface UserRow {
  id: string;
  email: string;
  name?: string;
  account_type: string;
  tier: string;
  is_active: boolean;
  created_at: string;
  last_seen_at?: string;
  msg_count: number;
  video_count: number;
}

interface Application {
  id: string; type: string; name: string; email: string;
  school_name?: string; subject?: string; inst_type?: string;
  country?: string; est_teachers?: number; est_students?: number;
  message?: string; created_at: string;
}

interface Invite {
  id: string; code: string; email?: string; note?: string;
  used_at?: string; expires_at: string; used_by_email?: string;
}

interface Stats {
  users_total: number; users_active: number; teachers_total: number;
  institutions: number; pending_applications: number; unused_invites: number;
  total_messages: number; total_videos: number;
}

export default function AdminPage() {
  const router = useRouter();
  const { user, token } = useSessionStore();

  const [stats,       setStats]       = useState<Stats | null>(null);
  const [users,       setUsers]       = useState<UserRow[]>([]);
  const [userTotal,   setUserTotal]   = useState(0);
  const [apps,        setApps]        = useState<Application[]>([]);
  const [invites,     setInvites]     = useState<Invite[]>([]);
  const [tab,         setTab]         = useState<Tab>('users');
  const [loading,     setLoading]     = useState(true);
  const [search,      setSearch]      = useState('');
  const [typeFilter,  setTypeFilter]  = useState('');
  const [newEmail,    setNewEmail]    = useState('');
  const [newNote,     setNewNote]     = useState('');
  const [creating,    setCreating]    = useState(false);
  const [lastCreds,   setLastCreds]   = useState<{ email: string; password: string; code: string } | null>(null);
  const [copied,      setCopied]      = useState(false);
  const [pwdUserId,   setPwdUserId]   = useState<string | null>(null);
  const [pwdValue,    setPwdValue]    = useState('');
  const [pwdLoading,  setPwdLoading]  = useState(false);

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
    } catch { /* ignore */ } finally { setLoading(false); }
  }

  const loadUsers = useCallback(async () => {
    const params = new URLSearchParams();
    if (search)     params.set('search', search);
    if (typeFilter) params.set('account_type', typeFilter);
    const res = await fetch(`${API_BASE}/api/admin/users?${params}`, { headers });
    const data = await res.json();
    setUsers(data.users ?? []);
    setUserTotal(data.total ?? 0);
  }, [search, typeFilter, token]);

  useEffect(() => { if (tab === 'users' && !loading) loadUsers(); }, [tab, search, typeFilter]);
  useEffect(() => { if (!loading) loadUsers(); }, [loading]);

  async function toggleActive(u: UserRow) {
    await fetch(`${API_BASE}/api/admin/users/${u.id}`, {
      method: 'PATCH', headers,
      body: JSON.stringify({ is_active: !u.is_active }),
    });
    loadUsers();
  }

  async function changePassword(userId: string) {
    if (!pwdValue || pwdValue.length < 8) { alert('Password must be at least 8 characters'); return; }
    setPwdLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/users/${userId}`, {
        method: 'PATCH', headers,
        body: JSON.stringify({ new_password: pwdValue }),
      });
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail); }
      setPwdUserId(null); setPwdValue('');
    } catch (err: any) {
      alert(err.message);
    } finally {
      setPwdLoading(false);
    }
  }

  async function review(id: string, action: 'approve' | 'reject') {
    const res = await fetch(`${API_BASE}/api/admin/applications/${id}/review`, {
      method: 'POST', headers, body: JSON.stringify({ action }),
    });
    const data = await res.json();
    if (!res.ok) { alert(data.detail || 'Failed'); return; }
    if (data.temp_password) {
      setLastCreds({ email: data.email, password: data.temp_password, code: data.invite_code ?? '' });
    } else if (data.invite_code) {
      alert(`Invite code: ${data.invite_code}`);
    }
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
      if (data.temp_password) {
        setLastCreds({ email: data.email, password: data.temp_password, code: data.code });
      } else {
        alert(`Invite code: ${data.code}`);
      }
      setNewEmail(''); setNewNote('');
      loadAll();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setCreating(false);
    }
  }

  function copyCredentials() {
    if (!lastCreds) return;
    const text = `Login: ${lastCreds.email}\nPassword: ${lastCreds.password}${lastCreds.code ? `\nInvite code: ${lastCreds.code}` : ''}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const inputCls = `bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                    text-[var(--tx1)] outline-none focus:border-purple-500/60 transition-colors`;

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center">
        <Loader2 size={32} className="text-purple-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--bg)] p-6">
      <div className="max-w-5xl mx-auto">

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-[var(--tx1)] text-2xl font-bold">Super Admin</h1>
          <p className="text-[var(--tx6)] text-sm mt-1">Platform overview and user management</p>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
            {[
              { label: 'Total users',    value: stats.users_total,          icon: Users },
              { label: 'Teachers',       value: stats.teachers_total,        icon: Users },
              { label: 'Messages sent',  value: stats.total_messages,        icon: MessageSquare },
              { label: 'Videos made',    value: stats.total_videos,          icon: Video },
              { label: 'Institutions',   value: stats.institutions,          icon: Building2 },
              { label: 'Pending apps',   value: stats.pending_applications,  icon: ClipboardList },
              { label: 'Active invites', value: stats.unused_invites,        icon: KeyRound },
              { label: 'Active users',   value: stats.users_active,          icon: Users },
            ].map(s => (
              <div key={s.label} className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-4 text-center">
                <s.icon size={16} className="text-purple-400 mx-auto mb-1" />
                <p className="text-[var(--tx1)] text-lg font-bold">{s.value.toLocaleString()}</p>
                <p className="text-[var(--tx7)] text-xs mt-0.5">{s.label}</p>
              </div>
            ))}
          </div>
        )}

        {/* Credentials popup */}
        {lastCreds && (
          <div className="mb-6 bg-green-500/10 border border-green-500/30 rounded-2xl p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-green-400 font-semibold text-sm mb-2">Account created — share these credentials</p>
                <p className="text-[var(--tx2)] text-sm font-mono">Email: <span className="text-white">{lastCreds.email}</span></p>
                <p className="text-[var(--tx2)] text-sm font-mono">Password: <span className="text-white">{lastCreds.password}</span></p>
                {lastCreds.code && <p className="text-[var(--tx2)] text-sm font-mono">Invite code: <span className="text-white">{lastCreds.code}</span></p>}
                <p className="text-[var(--tx7)] text-xs mt-2">Teacher can change the password from Settings after first login.</p>
              </div>
              <div className="flex gap-2 shrink-0">
                <button onClick={copyCredentials}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-green-500/20 hover:bg-green-500/30 text-green-400 text-xs rounded-lg transition-all">
                  {copied ? <><Check size={12} /> Copied</> : <><Copy size={12} /> Copy</>}
                </button>
                <button onClick={() => setLastCreds(null)}
                  className="text-[var(--tx8)] hover:text-[var(--tx4)] text-xs px-2">✕</button>
              </div>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 bg-[var(--surface)] border border-[var(--bd)] rounded-xl p-1 mb-6 w-fit">
          {([
            ['users',        `Users (${userTotal})`],
            ['applications', `Applications (${apps.length})`],
            ['invites',      `Invites (${invites.filter(i => !i.used_at).length} active)`],
          ] as const).map(([t, label]) => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-1.5 text-sm rounded-lg font-medium transition-all ${
                tab === t ? 'bg-purple-600 text-white' : 'text-[var(--tx6)] hover:text-[var(--tx2)]'
              }`}>
              {label}
            </button>
          ))}
        </div>

        {/* ── Users tab ──────────────────────────────────────────────────────── */}
        {tab === 'users' && (
          <div>
            {/* Filters */}
            <div className="flex gap-2 mb-4">
              <div className="relative flex-1">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--tx8)]" />
                <input
                  placeholder="Search by name or email…"
                  value={search} onChange={e => setSearch(e.target.value)}
                  className={`${inputCls} w-full pl-8`}
                />
              </div>
              <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)} className={inputCls}>
                <option value="">All types</option>
                <option value="student">Students</option>
                <option value="teacher">Teachers</option>
                <option value="institution_admin">Institution admins</option>
                <option value="super_admin">Super admins</option>
              </select>
            </div>

            <div className="space-y-2">
              {users.map(u => (
                <div key={u.id} className={`p-4 bg-[var(--surface)] border rounded-xl transition-all ${
                  u.is_active ? 'border-[var(--bd)]' : 'border-red-500/20 opacity-60'
                }`}>
                  <div className="flex items-center gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-[var(--tx1)] text-sm font-medium truncate">{u.name ?? u.email}</p>
                        {u.name && <p className="text-[var(--tx7)] text-xs truncate">{u.email}</p>}
                        <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                          u.account_type === 'teacher'           ? 'bg-blue-500/15 text-blue-400' :
                          u.account_type === 'institution_admin' ? 'bg-green-500/15 text-green-400' :
                          u.account_type === 'super_admin'       ? 'bg-purple-500/15 text-purple-400' :
                          'bg-[var(--ov1)] text-[var(--tx7)]'
                        }`}>{u.account_type}</span>
                        <span className="text-xs text-[var(--tx8)]">{u.tier}</span>
                      </div>
                      <div className="flex items-center gap-4 mt-1">
                        <span className="text-[var(--tx7)] text-xs flex items-center gap-1">
                          <MessageSquare size={10} /> {u.msg_count.toLocaleString()} msgs
                        </span>
                        <span className="text-[var(--tx7)] text-xs flex items-center gap-1">
                          <Video size={10} /> {u.video_count} videos
                        </span>
                        {u.last_seen_at && (
                          <span className="text-[var(--tx8)] text-xs">
                            Last seen {new Date(u.last_seen_at).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        onClick={() => { setPwdUserId(pwdUserId === u.id ? null : u.id); setPwdValue(''); }}
                        title="Change password"
                        className="text-[var(--tx8)] hover:text-purple-400 transition-colors"
                      >
                        <KeySquare size={18} />
                      </button>
                      <button
                        onClick={() => toggleActive(u)}
                        title={u.is_active ? 'Disable user' : 'Enable user'}
                        className="text-[var(--tx7)] hover:text-[var(--tx2)] transition-colors"
                      >
                        {u.is_active
                          ? <ToggleRight size={24} className="text-green-400" />
                          : <ToggleLeft  size={24} className="text-red-400" />}
                      </button>
                    </div>
                  </div>

                  {/* Inline password reset */}
                  {pwdUserId === u.id && (
                    <div className="mt-3 pt-3 border-t border-[var(--bd)] flex gap-2">
                      <input
                        autoFocus
                        type="password"
                        placeholder="New password (min 8 chars)"
                        value={pwdValue}
                        onChange={e => setPwdValue(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && changePassword(u.id)}
                        className={`${inputCls} flex-1`}
                      />
                      <button
                        onClick={() => changePassword(u.id)}
                        disabled={pwdLoading}
                        className="px-3 py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs rounded-lg transition-all disabled:opacity-40"
                      >
                        {pwdLoading ? <Loader2 size={13} className="animate-spin" /> : 'Set'}
                      </button>
                      <button
                        onClick={() => { setPwdUserId(null); setPwdValue(''); }}
                        className="px-3 py-2 text-[var(--tx7)] hover:text-[var(--tx2)] text-xs rounded-lg transition-all"
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </div>
              ))}
              {users.length === 0 && (
                <p className="text-[var(--tx6)] text-sm text-center py-12">No users found</p>
              )}
            </div>
          </div>
        )}

        {/* ── Applications tab ───────────────────────────────────────────────── */}
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
                    {(a.est_teachers || a.est_students) && (
                      <p className="text-[var(--tx6)] text-xs">~{a.est_teachers} teachers, ~{a.est_students} students</p>
                    )}
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

        {/* ── Invites tab ────────────────────────────────────────────────────── */}
        {tab === 'invites' && (
          <div className="space-y-4">
            <form onSubmit={createInvite} className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5">
              <p className="text-[var(--tx2)] text-sm font-medium mb-1">Generate invite code</p>
              <p className="text-[var(--tx7)] text-xs mb-3">
                If you enter an email, an account is created with a temporary password you can share immediately.
              </p>
              <div className="flex gap-2 flex-wrap">
                <input
                  type="email" placeholder="Email (optional)"
                  value={newEmail} onChange={e => setNewEmail(e.target.value)}
                  className={`${inputCls} flex-1 min-w-[200px]`}
                />
                <input
                  placeholder="Note (optional)"
                  value={newNote} onChange={e => setNewNote(e.target.value)}
                  className={`${inputCls} flex-1 min-w-[160px]`}
                />
                <button type="submit" disabled={creating}
                  className="flex items-center gap-1.5 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl transition-all disabled:opacity-40">
                  {creating ? <Loader2 size={14} className="animate-spin" /> : <><Plus size={14} /> Create</>}
                </button>
              </div>
            </form>

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
                  <span className="text-[var(--tx8)] text-xs shrink-0">
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
