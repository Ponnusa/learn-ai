'use client';
import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  ArrowLeft, Users, Copy, Check, Trash2, Loader2, UserX,
  UserPlus, Search, X, ChevronDown, ChevronUp,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';
import { useTranslation } from '@/hooks/useTranslation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Student {
  id: string;
  email: string;
  name?: string;
  joined_at: string;
  last_seen_at?: string;
}

interface AvailableStudent {
  id: string;
  name?: string;
  email: string;
  source_classrooms: string[];
}

interface Credential {
  name: string;
  email: string;
  password: string;
}

interface Classroom {
  id: string;
  name: string;
  subject?: string;
  grade?: string;
  join_code: string;
  is_active: boolean;
  student_count: number;
  students: Student[];
}

type ModalTab = 'existing' | 'new';

export default function ClassroomDetailPage() {
  const router      = useRouter();
  const params      = useParams();
  const classroomId = params.id as string;
  const { user, token } = useSessionStore();

  const { t, tF } = useTranslation();
  const [cls,       setCls]       = useState<Classroom | null>(null);
  const [loading,   setLoading]   = useState(true);
  const [copied,    setCopied]    = useState(false);
  const [removing,  setRemoving]  = useState<string | null>(null);
  const [archiving, setArchiving] = useState(false);

  // Add-students modal
  const [showModal,   setShowModal]   = useState(false);
  const [modalTab,    setModalTab]    = useState<ModalTab>('existing');

  // Existing-students tab
  const [available,   setAvailable]   = useState<AvailableStudent[]>([]);
  const [avLoading,   setAvLoading]   = useState(false);
  const [search,      setSearch]      = useState('');
  const [selected,    setSelected]    = useState<Set<string>>(new Set());
  const [enrolling,   setEnrolling]   = useState(false);
  const [enrolledMsg, setEnrolledMsg] = useState('');

  // New-students tab
  const [names,        setNames]        = useState('');
  const [password,     setPassword]     = useState('');
  const [provisioning, setProvisioning] = useState(false);
  const [credentials,  setCredentials]  = useState<Credential[]>([]);
  const [credCopied,   setCredCopied]   = useState(false);

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    if (!user) { router.replace('/auth/teacher'); return; }
    load();
  }, [user, classroomId]);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/classrooms/${classroomId}`, { headers });
      if (!res.ok) { router.replace('/teacher/classrooms'); return; }
      const data = await res.json();
      setCls(data);
      setPassword(data.join_code);          // default password = join code
    } finally {
      setLoading(false);
    }
  }

  async function removeStudent(studentId: string) {
    setRemoving(studentId);
    try {
      await fetch(`${API_BASE}/api/classrooms/${classroomId}/students/${studentId}`, {
        method: 'DELETE', headers,
      });
      setCls(prev => prev ? {
        ...prev,
        students: prev.students.filter(s => s.id !== studentId),
        student_count: prev.student_count - 1,
      } : prev);
    } finally {
      setRemoving(null);
    }
  }

  async function toggleArchive() {
    if (!cls) return;
    setArchiving(true);
    try {
      await fetch(`${API_BASE}/api/classrooms/${classroomId}`, {
        method: 'PATCH', headers,
        body: JSON.stringify({ is_active: !cls.is_active }),
      });
      setCls(prev => prev ? { ...prev, is_active: !prev.is_active } : prev);
    } finally {
      setArchiving(false);
    }
  }

  function copyCode() {
    if (!cls) return;
    navigator.clipboard.writeText(cls.join_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function openModal() {
    setShowModal(true);
    setModalTab('existing');
    setSelected(new Set());
    setSearch('');
    setEnrolledMsg('');
    setCredentials([]);
    setCredCopied(false);
    setAvLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/classrooms/${classroomId}/students/available`, { headers });
      if (res.ok) setAvailable(await res.json());
    } finally {
      setAvLoading(false);
    }
  }

  function closeModal() {
    setShowModal(false);
    setAvailable([]);
    setSelected(new Set());
    setNames('');
    setCredentials([]);
    setEnrolledMsg('');
  }

  function toggleSelect(id: string) {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const filtered = available.filter(s =>
    (s.name ?? s.email).toLowerCase().includes(search.toLowerCase())
  );

  async function enrollSelected() {
    if (selected.size === 0) return;
    setEnrolling(true);
    try {
      const res = await fetch(`${API_BASE}/api/classrooms/${classroomId}/students/enroll`, {
        method: 'POST', headers,
        body: JSON.stringify({ student_ids: [...selected] }),
      });
      const data = await res.json();
      setEnrolledMsg(tF(t.teacher.studentsAdded, { n: data.enrolled }));
      setSelected(new Set());
      setAvailable(prev => prev.filter(s => !selected.has(s.id)));
      await load();
    } finally {
      setEnrolling(false);
    }
  }

  async function provisionStudents() {
    const nameList = names.split('\n').map(n => n.trim()).filter(Boolean);
    if (nameList.length === 0) return;
    setProvisioning(true);
    try {
      const res = await fetch(`${API_BASE}/api/classrooms/${classroomId}/students/provision`, {
        method: 'POST', headers,
        body: JSON.stringify({ names: nameList, password }),
      });
      const data = await res.json();
      setCredentials(data.credentials);
      setNames('');
      await load();
    } finally {
      setProvisioning(false);
    }
  }

  function copyAllCredentials() {
    const text = credentials
      .map(c => `${c.name}\t${c.email}\t${c.password}`)
      .join('\n');
    navigator.clipboard.writeText(`Name\tLogin Email\tPassword\n${text}`);
    setCredCopied(true);
    setTimeout(() => setCredCopied(false), 2000);
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center">
        <Loader2 size={28} className="text-purple-400 animate-spin" />
      </div>
    );
  }

  if (!cls) return null;

  return (
    <div className="min-h-screen bg-[var(--bg)] p-6">
      <div className="max-w-3xl mx-auto">

        {/* Back */}
        <button onClick={() => router.push('/teacher/classrooms')}
          className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm mb-6 transition-colors">
          <ArrowLeft size={15} /> {t.teacher.backToClassrooms}
        </button>

        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-[var(--tx1)] text-2xl font-bold">{cls.name}</h1>
              {!cls.is_active && (
                <span className="text-xs px-2 py-0.5 bg-[var(--ov1)] text-[var(--tx7)] rounded-full">{t.teacher.archived}</span>
              )}
            </div>
            <p className="text-[var(--tx6)] text-sm mt-1">
              {[cls.subject, cls.grade].filter(Boolean).join(' · ')}
              {cls.student_count > 0 && ` · ${cls.student_count} student${cls.student_count !== 1 ? 's' : ''}`}
            </p>
          </div>
          <button
            onClick={toggleArchive}
            disabled={archiving}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-[var(--bd)] hover:border-[var(--tx6)]
                       text-[var(--tx6)] hover:text-[var(--tx2)] text-xs rounded-xl transition-all disabled:opacity-40"
          >
            {archiving ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
            {cls.is_active ? t.teacher.archiveClassroom : t.teacher.reopenClassroom}
          </button>
        </div>

        {/* Join code */}
        <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-6">
          <p className="text-[var(--tx6)] text-xs mb-1">{t.teacher.studentJoinCode}</p>
          <div className="flex items-center justify-between">
            <p className="text-purple-400 font-mono text-3xl font-bold tracking-[0.25em]">{cls.join_code}</p>
            <button onClick={copyCode}
              className="flex items-center gap-1.5 px-3 py-2 bg-purple-600/15 hover:bg-purple-600/25
                         text-purple-400 text-sm rounded-xl transition-all">
              {copied ? <><Check size={14} /> {t.teacher.copied}</> : <><Copy size={14} /> {t.teacher.copyCode}</>}
            </button>
          </div>
          <p className="text-[var(--tx8)] text-xs mt-3">
            Students go to{' '}
            <span className="text-[var(--tx5)] font-mono">learnx-ai.com/join</span>
            {' '}and enter code{' '}
            <strong className="text-[var(--tx6)] font-mono">{cls.join_code}</strong>
          </p>
        </div>

        {/* Student roster */}
        <div>
          <div className="flex items-center justify-between gap-2 mb-4">
            <div className="flex items-center gap-2">
              <Users size={16} className="text-[var(--tx6)]" />
              <h2 className="text-[var(--tx1)] font-semibold">
                {tF(t.teacher.studentsCountLabel, { n: cls.student_count })}
              </h2>
            </div>
            <button
              onClick={openModal}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600 hover:bg-purple-500
                         text-white text-xs font-medium rounded-xl transition-colors"
            >
              <UserPlus size={13} /> {t.teacher.addStudents}
            </button>
          </div>

          {cls.students.length === 0 ? (
            <div className="text-center py-12 bg-[var(--surface)] border border-[var(--bd)] rounded-2xl">
              <Users size={32} className="text-[var(--tx8)] mx-auto mb-3" />
              <p className="text-[var(--tx5)] text-sm">{t.teacher.noStudents}</p>
              <p className="text-[var(--tx7)] text-xs mt-1">{t.teacher.noStudentsHint}</p>
            </div>
          ) : (
            <div className="space-y-2">
              {cls.students.map(s => (
                <div key={s.id}
                  className="flex items-center gap-4 p-4 bg-[var(--surface)] border border-[var(--bd)] rounded-xl">
                  <div className="w-8 h-8 rounded-full bg-purple-600/20 flex items-center justify-center shrink-0">
                    <span className="text-purple-400 text-xs font-bold">
                      {(s.name ?? s.email)[0].toUpperCase()}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[var(--tx1)] text-sm font-medium truncate">{s.name ?? s.email}</p>
                    {s.name && <p className="text-[var(--tx7)] text-xs truncate">{s.email}</p>}
                    <p className="text-[var(--tx8)] text-xs mt-0.5">
                      {tF(t.teacher.joinedDate, { date: new Date(s.joined_at).toLocaleDateString() })}
                      {s.last_seen_at && ` · ${tF(t.teacher.lastSeenDate, { date: new Date(s.last_seen_at).toLocaleDateString() })}`}
                    </p>
                  </div>
                  <button
                    onClick={() => removeStudent(s.id)}
                    disabled={removing === s.id}
                    title={t.teacher.removeStudent}
                    className="text-[var(--tx8)] hover:text-red-400 transition-colors disabled:opacity-40 shrink-0"
                  >
                    {removing === s.id
                      ? <Loader2 size={15} className="animate-spin" />
                      : <UserX size={15} />}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Add Students Modal ── */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
          onClick={e => { if (e.target === e.currentTarget) closeModal(); }}>
          <div className="w-full max-w-lg bg-[var(--surface)] border border-[var(--bd)] rounded-2xl shadow-2xl
                          flex flex-col max-h-[85vh]">

            {/* Modal header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--bd)] shrink-0">
              <h3 className="text-[var(--tx1)] font-semibold">{t.teacher.addStudentsTitle}</h3>
              <button onClick={closeModal} className="text-[var(--tx6)] hover:text-[var(--tx1)] transition-colors">
                <X size={18} />
              </button>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-[var(--bd)] shrink-0">
              {(['existing', 'new'] as ModalTab[]).map(tab => (
                <button
                  key={tab}
                  onClick={() => { setModalTab(tab); setEnrolledMsg(''); setCredentials([]); }}
                  className={`flex-1 py-2.5 text-sm font-medium transition-colors ${
                    modalTab === tab
                      ? 'text-purple-400 border-b-2 border-purple-500'
                      : 'text-[var(--tx6)] hover:text-[var(--tx2)]'
                  }`}
                >
                  {tab === 'existing' ? t.teacher.existingStudentsTab : t.teacher.newStudentsTab}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="flex-1 overflow-y-auto p-5 space-y-4">

              {/* ── Existing students tab ── */}
              {modalTab === 'existing' && (
                <>
                  {enrolledMsg && (
                    <p className="text-green-400 text-sm text-center py-1">{enrolledMsg}</p>
                  )}

                  <div className="relative">
                    <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--tx7)]" />
                    <input
                      value={search}
                      onChange={e => setSearch(e.target.value)}
                      placeholder={t.teacher.searchStudentsPlaceholder}
                      className="w-full pl-8 pr-3 py-2 rounded-xl bg-[var(--bg)] border border-[var(--bd)]
                                 text-[var(--tx1)] text-sm placeholder-[var(--tx7)]
                                 focus:outline-none focus:border-purple-500/50"
                    />
                  </div>

                  {avLoading ? (
                    <div className="flex justify-center py-8">
                      <Loader2 size={20} className="text-purple-400 animate-spin" />
                    </div>
                  ) : filtered.length === 0 ? (
                    <p className="text-[var(--tx7)] text-sm text-center py-8">
                      {t.teacher.noExistingStudents}
                    </p>
                  ) : (
                    <div className="space-y-1.5">
                      {filtered.map(s => (
                        <label key={s.id}
                          className="flex items-center gap-3 p-3 rounded-xl hover:bg-[var(--ov1)]
                                     cursor-pointer transition-colors">
                          <input
                            type="checkbox"
                            checked={selected.has(s.id)}
                            onChange={() => toggleSelect(s.id)}
                            className="accent-purple-500 w-4 h-4 shrink-0"
                          />
                          <div className="flex-1 min-w-0">
                            <p className="text-[var(--tx1)] text-sm font-medium truncate">
                              {s.name ?? s.email}
                            </p>
                            {s.name && <p className="text-[var(--tx7)] text-xs truncate">{s.email}</p>}
                          </div>
                          {s.source_classrooms.length > 0 && (
                            <span className="text-[10px] text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded-full shrink-0">
                              {tF(t.teacher.fromClassroomLabel, { name: s.source_classrooms[0] })}
                            </span>
                          )}
                        </label>
                      ))}
                    </div>
                  )}
                </>
              )}

              {/* ── New students tab ── */}
              {modalTab === 'new' && (
                <>
                  {credentials.length > 0 ? (
                    /* Credentials table */
                    <div className="space-y-3">
                      <p className="text-green-400 text-sm font-medium">
                        {tF(t.teacher.credentialsReady, { n: credentials.length })}
                      </p>
                      <div className="rounded-xl border border-[var(--bd)] overflow-hidden text-xs">
                        <table className="w-full">
                          <thead>
                            <tr className="bg-[var(--ov1)] text-[var(--tx6)]">
                              <th className="px-3 py-2 text-left font-medium">Name</th>
                              <th className="px-3 py-2 text-left font-medium">{t.teacher.loginEmailCol}</th>
                              <th className="px-3 py-2 text-left font-medium">Password</th>
                            </tr>
                          </thead>
                          <tbody>
                            {credentials.map((c, i) => (
                              <tr key={i} className="border-t border-[var(--bd)]">
                                <td className="px-3 py-2 text-[var(--tx1)]">{c.name}</td>
                                <td className="px-3 py-2 text-[var(--tx2)] font-mono">{c.email}</td>
                                <td className="px-3 py-2 text-[var(--tx2)] font-mono">{c.password}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <button onClick={copyAllCredentials}
                        className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-xl
                                   border border-[var(--bd)] text-[var(--tx6)] hover:text-[var(--tx2)]
                                   transition-colors">
                        {credCopied
                          ? <><Check size={12} /> {t.teacher.credentialsCopied}</>
                          : <><Copy size={12} /> {t.teacher.copyAllCredentials}</>}
                      </button>
                      <button onClick={() => setCredentials([])}
                        className="text-xs text-purple-400 hover:text-purple-300 transition-colors">
                        + Add more students
                      </button>
                    </div>
                  ) : (
                    /* Name entry form */
                    <div className="space-y-4">
                      <div>
                        <label className="block text-[var(--tx6)] text-xs mb-1.5">
                          {t.teacher.studentNamesLabel}
                        </label>
                        <textarea
                          value={names}
                          onChange={e => setNames(e.target.value)}
                          placeholder={t.teacher.studentNamesPlaceholder}
                          rows={6}
                          className="w-full px-3 py-2.5 rounded-xl bg-[var(--bg)] border border-[var(--bd)]
                                     text-[var(--tx1)] text-sm placeholder-[var(--tx7)] resize-none
                                     focus:outline-none focus:border-purple-500/50"
                        />
                        <p className="text-[var(--tx8)] text-xs mt-1">
                          {names.split('\n').filter(n => n.trim()).length} names
                        </p>
                      </div>
                      <div>
                        <label className="block text-[var(--tx6)] text-xs mb-1.5">
                          {t.teacher.defaultPasswordLabel}
                        </label>
                        <input
                          type="text"
                          value={password}
                          onChange={e => setPassword(e.target.value)}
                          className="w-full px-3 py-2.5 rounded-xl bg-[var(--bg)] border border-[var(--bd)]
                                     text-[var(--tx1)] text-sm font-mono
                                     focus:outline-none focus:border-purple-500/50"
                        />
                        <p className="text-[var(--tx8)] text-xs mt-1">
                          Pre-filled with the join code — students can change it later
                        </p>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Modal footer */}
            {!credentials.length && (
              <div className="px-5 py-4 border-t border-[var(--bd)] shrink-0 flex justify-end gap-2">
                <button onClick={closeModal}
                  className="px-4 py-2 text-sm text-[var(--tx6)] hover:text-[var(--tx2)] transition-colors">
                  {t.cancel}
                </button>
                {modalTab === 'existing' ? (
                  <button
                    onClick={enrollSelected}
                    disabled={selected.size === 0 || enrolling}
                    className="flex items-center gap-1.5 px-4 py-2 bg-purple-600 hover:bg-purple-500
                               text-white text-sm rounded-xl transition-colors disabled:opacity-40"
                  >
                    {enrolling
                      ? <><Loader2 size={13} className="animate-spin" /> {t.teacher.addingStudents}</>
                      : tF(t.teacher.addSelected, { n: selected.size })}
                  </button>
                ) : (
                  <button
                    onClick={provisionStudents}
                    disabled={!names.trim() || !password.trim() || provisioning}
                    className="flex items-center gap-1.5 px-4 py-2 bg-purple-600 hover:bg-purple-500
                               text-white text-sm rounded-xl transition-colors disabled:opacity-40"
                  >
                    {provisioning
                      ? <><Loader2 size={13} className="animate-spin" /> {t.teacher.provisioningBtn}</>
                      : t.teacher.provisionBtn}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
