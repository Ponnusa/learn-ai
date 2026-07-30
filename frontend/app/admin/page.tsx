'use client';
import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  CheckCircle, XCircle, Plus, Loader2, Building2, Users,
  KeyRound, ClipboardList, MessageSquare, Video, Search,
  ToggleLeft, ToggleRight, Copy, Check, KeySquare,
  ChevronDown, UserPlus, GraduationCap,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type Tab = 'users' | 'applications' | 'invites' | 'institutions';

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

interface InstitutionRow {
  id: string; name: string; type: string; plan: string; country?: string;
  language?: string | null;
  max_teachers: number; max_students: number;
  teacher_count: number; student_count: number; created_at: string;
}

interface InstMember {
  id: string; email: string; name?: string; status: string; joined_at?: string;
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

  // Institutions tab
  const [institutions,      setInstitutions]      = useState<InstitutionRow[]>([]);
  const [newInstName,       setNewInstName]       = useState('');
  const [newInstAdminName,  setNewInstAdminName]  = useState('');
  const [newInstPlan,       setNewInstPlan]       = useState('trial');
  const [newInstLang,       setNewInstLang]       = useState('');
  const [creatingInst,      setCreatingInst]      = useState(false);
  const [instLastCreds,     setInstLastCreds]     = useState<{ email: string; password: string; instName: string } | null>(null);
  const [instCopied,        setInstCopied]        = useState(false);
  const [expandedInst,      setExpandedInst]      = useState<string | null>(null);
  const [instMembers,       setInstMembers]       = useState<Record<string, InstMember[]>>({});
  const [instMembersLoading,setInstMembersLoading]= useState<string | null>(null);
  const [newTeacherName,    setNewTeacherName]    = useState<Record<string, string>>({});
  const [provisioningTeacher,setProvisioningTeacher] = useState<string | null>(null);
  const [teacherCreds,      setTeacherCreds]      = useState<Record<string, { name: string; email: string; password: string }[]>>({});
  const [tcCopied,          setTcCopied]          = useState<string | null>(null);
  const [instLangValue,     setInstLangValue]     = useState<Record<string, string>>({});
  const [savingInstLang,    setSavingInstLang]    = useState<string | null>(null);

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    if (!user) { router.replace('/auth/login'); return; }
    if (user.account_type !== 'super_admin') { router.replace('/'); return; }
    loadAll();
  }, [user]);

  async function loadAll() {
    setLoading(true);
    try {
      const [sRes, aRes, iRes, instRes] = await Promise.all([
        fetch(`${API_BASE}/api/admin/stats`, { headers }),
        fetch(`${API_BASE}/api/admin/applications?status=pending`, { headers }),
        fetch(`${API_BASE}/api/admin/invites`, { headers }),
        fetch(`${API_BASE}/api/admin/institutions`, { headers }),
      ]);
      setStats(await sRes.json());
      setApps(await aRes.json());
      setInvites(await iRes.json());
      if (instRes.ok) setInstitutions(await instRes.json());
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

  async function createInstitution() {
    if (!newInstName.trim() || !newInstAdminName.trim()) return;
    setCreatingInst(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/institutions`, {
        method: 'POST', headers,
        body: JSON.stringify({ name: newInstName, admin_name: newInstAdminName, plan: newInstPlan, language: newInstLang || null }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed');
      setInstLastCreds({ email: data.email, password: data.temp_password, instName: newInstName });
      setNewInstName(''); setNewInstAdminName(''); setNewInstPlan('trial'); setNewInstLang('');
      loadAll();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setCreatingInst(false);
    }
  }

  function copyInstCredentials() {
    if (!instLastCreds) return;
    navigator.clipboard.writeText(`Login: ${instLastCreds.email}\nPassword: ${instLastCreds.password}`);
    setInstCopied(true);
    setTimeout(() => setInstCopied(false), 2000);
  }

  async function toggleInst(instId: string) {
    if (expandedInst === instId) { setExpandedInst(null); return; }
    setExpandedInst(instId);
    // seed the language editor with the current value
    const inst = institutions.find(i => i.id === instId);
    if (inst && instLangValue[instId] === undefined) {
      setInstLangValue(p => ({ ...p, [instId]: inst.language ?? '' }));
    }
    if (!instMembers[instId]) {
      setInstMembersLoading(instId);
      try {
        await loadInstMembers(instId);
      } catch { /* ignore */ } finally {
        setInstMembersLoading(null);
      }
    }
  }

  async function updateInstLanguage(instId: string) {
    setSavingInstLang(instId);
    try {
      const lang = instLangValue[instId] || null;
      const res = await fetch(`${API_BASE}/api/admin/institutions/${instId}/language`, {
        method: 'PATCH', headers,
        body: JSON.stringify({ language: lang }),
      });
      if (res.ok) {
        setInstitutions(prev => prev.map(i => i.id === instId ? { ...i, language: lang } : i));
      } else {
        const d = await res.json();
        alert(d.detail || 'Failed to update language');
      }
    } catch { alert('Request failed'); }
    finally { setSavingInstLang(null); }
  }

  async function loadInstMembers(instId: string) {
    const res = await fetch(`${API_BASE}/api/institutions/${instId}/members?role=teacher`, { headers });
    if (res.ok) {
      const data = await res.json();
      setInstMembers(p => ({ ...p, [instId]: data }));
    }
  }

  async function provisionTeacher(instId: string) {
    const name = newTeacherName[instId]?.trim();
    if (!name) return;
    setProvisioningTeacher(instId);
    try {
      const res = await fetch(`${API_BASE}/api/institutions/${instId}/teachers/provision`, {
        method: 'POST', headers,
        body: JSON.stringify({ name }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed');
      setTeacherCreds(p => ({ ...p, [instId]: [...(p[instId] || []), data] }));
      setNewTeacherName(p => ({ ...p, [instId]: '' }));
      await loadInstMembers(instId);
      loadAll();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setProvisioningTeacher(null);
    }
  }

  function copyTeacherCreds(instId: string) {
    const creds = teacherCreds[instId] || [];
    const text = creds.map(c => `${c.name}\t${c.email}\t${c.password}`).join('\n');
    navigator.clipboard.writeText(`Name\tEmail\tPassword\n${text}`);
    setTcCopied(instId);
    setTimeout(() => setTcCopied(null), 2000);
  }

  function copyCredentials() {
    if (!lastCreds) return;
    const text = `Login: ${lastCreds.email}\nPassword: ${lastCreds.password}${lastCreds.code ? `\nInvite code: ${lastCreds.code}` : ''}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const inputCls = `bg-[var(--input)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
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
            ['institutions', `Institutions (${institutions.length})`],
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

        {/* ── Institutions tab ──────────────────────────────────────────────── */}
        {tab === 'institutions' && (
          <div className="space-y-4">

            {/* Create institution */}
            <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5">
              <p className="text-[var(--tx2)] text-sm font-medium mb-3">Create Institution</p>
              <div className="grid grid-cols-2 gap-2 mb-3">
                <input
                  placeholder="Institution name"
                  value={newInstName} onChange={e => setNewInstName(e.target.value)}
                  className={`${inputCls} col-span-2`}
                />
                <input
                  placeholder="Admin name (e.g. John Smith)"
                  value={newInstAdminName} onChange={e => setNewInstAdminName(e.target.value)}
                  className={inputCls}
                />
                <select value={newInstPlan} onChange={e => setNewInstPlan(e.target.value)} className={inputCls}>
                  <option value="trial">Trial</option>
                  <option value="basic">Basic</option>
                  <option value="pro">Pro</option>
                </select>
                <select value={newInstLang} onChange={e => setNewInstLang(e.target.value)} className={`${inputCls} col-span-2`}>
                  <option value="">No language lock (users choose freely)</option>
                  <option value="en">🇬🇧 English</option>
                  <option value="fi">🇫🇮 Suomi (Finnish)</option>
                  <option value="sv">🇸🇪 Svenska (Swedish)</option>
                  <option value="es">🇪🇸 Español (Spanish)</option>
                  <option value="fr">🇫🇷 Français (French)</option>
                </select>
              </div>
              <p className="text-[var(--tx8)] text-xs mb-3">
                Admin login will be auto-generated as <span className="font-mono text-purple-400">admin.{'{'}inst-name{'}'}</span>@learnxai.app
              </p>
              <button
                onClick={createInstitution}
                disabled={creatingInst || !newInstName.trim() || !newInstAdminName.trim()}
                className="flex items-center gap-1.5 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl transition-all disabled:opacity-40"
              >
                {creatingInst ? <Loader2 size={14} className="animate-spin" /> : <><Plus size={14} /> Create Institution</>}
              </button>
            </div>

            {/* Institution admin credentials popup */}
            {instLastCreds && (
              <div className="bg-green-500/10 border border-green-500/30 rounded-2xl p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-green-400 font-semibold text-sm mb-2">
                      Institution "{instLastCreds.instName}" created — share admin credentials
                    </p>
                    <p className="text-[var(--tx2)] text-sm font-mono">Email: <span className="text-white">{instLastCreds.email}</span></p>
                    <p className="text-[var(--tx2)] text-sm font-mono">Password: <span className="text-white">{instLastCreds.password}</span></p>
                    <p className="text-[var(--tx7)] text-xs mt-2">Institution admin can change password from Settings after first login.</p>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button onClick={copyInstCredentials}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-green-500/20 hover:bg-green-500/30 text-green-400 text-xs rounded-lg transition-all">
                      {instCopied ? <><Check size={12} /> Copied</> : <><Copy size={12} /> Copy</>}
                    </button>
                    <button onClick={() => setInstLastCreds(null)} className="text-[var(--tx8)] hover:text-[var(--tx4)] text-xs px-2">✕</button>
                  </div>
                </div>
              </div>
            )}

            {/* Institution list */}
            {institutions.length === 0 && (
              <p className="text-[var(--tx6)] text-sm text-center py-12">No institutions yet</p>
            )}
            {institutions.map(inst => (
              <div key={inst.id} className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl overflow-hidden">

                {/* Header row */}
                <button
                  className="w-full flex items-center justify-between p-4 hover:bg-[var(--ov1)] transition-colors text-left"
                  onClick={() => toggleInst(inst.id)}
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <Building2 size={15} className="text-purple-400" />
                      <p className="text-[var(--tx1)] font-medium">{inst.name}</p>
                      <span className="text-xs px-1.5 py-0.5 rounded-full bg-purple-500/15 text-purple-400 capitalize">{inst.plan}</span>
                      {inst.language && (
                        <span className="text-xs px-1.5 py-0.5 rounded-full bg-blue-500/15 text-blue-400 uppercase">{inst.language}</span>
                      )}
                    </div>
                    <p className="text-[var(--tx7)] text-xs mt-0.5 pl-5">
                      <GraduationCap size={10} className="inline mr-1" />{inst.teacher_count}/{inst.max_teachers} teachers ·{' '}
                      <Users size={10} className="inline mr-1" />{inst.student_count}/{inst.max_students} students
                      {inst.country ? ` · ${inst.country}` : ''}
                    </p>
                  </div>
                  <ChevronDown size={16} className={`text-[var(--tx7)] transition-transform ${expandedInst === inst.id ? 'rotate-180' : ''}`} />
                </button>

                {/* Expanded: language + teachers + add form */}
                {expandedInst === inst.id && (
                  <div className="border-t border-[var(--bd)] p-4 space-y-4">

                    {/* Language setting */}
                    <div>
                      <p className="text-[var(--tx5)] text-xs font-medium mb-2 uppercase tracking-wide">Institution Language</p>
                      <div className="flex gap-2">
                        <select
                          value={instLangValue[inst.id] ?? (inst.language ?? '')}
                          onChange={e => setInstLangValue(p => ({ ...p, [inst.id]: e.target.value }))}
                          className={`${inputCls} flex-1`}
                        >
                          <option value="">No lock — users choose freely</option>
                          <option value="en">🇬🇧 English</option>
                          <option value="fi">🇫🇮 Suomi (Finnish)</option>
                          <option value="sv">🇸🇪 Svenska (Swedish)</option>
                          <option value="es">🇪🇸 Español (Spanish)</option>
                          <option value="fr">🇫🇷 Français (French)</option>
                        </select>
                        <button
                          onClick={() => updateInstLanguage(inst.id)}
                          disabled={savingInstLang === inst.id}
                          className="flex items-center gap-1.5 px-3 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl transition-all disabled:opacity-40"
                        >
                          {savingInstLang === inst.id ? <Loader2 size={13} className="animate-spin" /> : 'Save'}
                        </button>
                      </div>
                    </div>

                    {/* Teacher list */}
                    {instMembersLoading === inst.id ? (
                      <div className="flex items-center gap-2 text-[var(--tx7)] text-sm">
                        <Loader2 size={14} className="animate-spin" /> Loading teachers…
                      </div>
                    ) : (
                      <div>
                        <p className="text-[var(--tx5)] text-xs font-medium mb-2 uppercase tracking-wide">Teachers</p>
                        {(instMembers[inst.id] || []).length === 0 ? (
                          <p className="text-[var(--tx7)] text-sm">No teachers yet — add one below.</p>
                        ) : (
                          <div className="space-y-1.5">
                            {(instMembers[inst.id] || []).map(m => (
                              <div key={m.id} className="flex items-center justify-between px-3 py-2 rounded-lg bg-[var(--ov1)]">
                                <div>
                                  <span className="text-[var(--tx2)] text-sm">{m.name || m.email}</span>
                                  {m.name && <span className="text-[var(--tx7)] text-xs ml-2 font-mono">{m.email}</span>}
                                </div>
                                <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                                  m.status === 'active' ? 'bg-green-500/15 text-green-400' : 'bg-yellow-500/15 text-yellow-400'
                                }`}>{m.status}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Add teacher form */}
                    <div>
                      <p className="text-[var(--tx5)] text-xs font-medium mb-2 uppercase tracking-wide">Add Teacher</p>
                      <div className="flex gap-2">
                        <input
                          placeholder="Teacher name (e.g. Sarah Jones)"
                          value={newTeacherName[inst.id] || ''}
                          onChange={e => setNewTeacherName(p => ({ ...p, [inst.id]: e.target.value }))}
                          onKeyDown={e => e.key === 'Enter' && provisionTeacher(inst.id)}
                          className={`${inputCls} flex-1`}
                        />
                        <button
                          onClick={() => provisionTeacher(inst.id)}
                          disabled={provisioningTeacher === inst.id || !newTeacherName[inst.id]?.trim()}
                          className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-xl transition-all disabled:opacity-40"
                        >
                          {provisioningTeacher === inst.id
                            ? <Loader2 size={13} className="animate-spin" />
                            : <><UserPlus size={13} /> Add</>}
                        </button>
                      </div>
                      <p className="text-[var(--tx8)] text-xs mt-1.5">
                        Login will be <span className="font-mono text-purple-400">{'{'}name{'}'}.{'{'}inst{'}'}</span>@learnxai.app with a generated password.
                      </p>
                    </div>

                    {/* New teacher credentials */}
                    {(teacherCreds[inst.id] || []).length > 0 && (
                      <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
                        <div className="flex items-center justify-between mb-2">
                          <p className="text-blue-400 text-sm font-medium">New teacher credentials — share these</p>
                          <button
                            onClick={() => copyTeacherCreds(inst.id)}
                            className="flex items-center gap-1 px-2.5 py-1 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 text-xs rounded-lg transition-all"
                          >
                            {tcCopied === inst.id ? <><Check size={11} /> Copied</> : <><Copy size={11} /> Copy all</>}
                          </button>
                        </div>
                        <div className="overflow-x-auto">
                          <table className="w-full text-xs">
                            <thead>
                              <tr className="text-[var(--tx7)] border-b border-[var(--bd)]">
                                <th className="text-left pb-1.5 pr-4">Name</th>
                                <th className="text-left pb-1.5 pr-4">Email</th>
                                <th className="text-left pb-1.5">Password</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(teacherCreds[inst.id] || []).map((c, i) => (
                                <tr key={i} className="border-b border-[var(--bd)]/50 last:border-0">
                                  <td className="py-1.5 pr-4 text-[var(--tx2)]">{c.name}</td>
                                  <td className="py-1.5 pr-4 font-mono text-purple-300">{c.email}</td>
                                  <td className="py-1.5 font-mono text-[var(--tx2)]">{c.password}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                  </div>
                )}
              </div>
            ))}

          </div>
        )}

      </div>
    </div>
  );
}
