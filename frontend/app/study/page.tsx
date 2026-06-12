'use client';
import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import {
  BookOpen, Plus, Loader, X, Upload,
  FileText, Brain, LayoutGrid, Trash2,
} from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { useSessionStore } from '@/store/sessionStore';
import { createStudySet, listStudySets, deleteStudySet, StudySetSummary } from '@/lib/api';

// ─── Helpers ─────────────────────────────────────────────────────────────────

const SUBJECT_OPTS = ['Mathematics', 'Physics', 'Chemistry', 'Biology', 'History', 'Economics', 'Computer Science', 'Other'];

const STATUS_STYLE: Record<string, string> = {
  empty:      'text-[var(--tx6)] bg-[var(--ov3)]',
  processing: 'text-yellow-400 bg-yellow-500/10',
  ready:      'text-emerald-400 bg-emerald-500/10',
  failed:     'text-red-400 bg-red-500/10',
};
const STATUS_LABEL: Record<string, string> = {
  empty: 'No material', processing: 'Processing…', ready: 'Ready', failed: 'Failed',
};

function formatDate(iso: string) {
  const d = new Date(iso);
  const diff = Math.floor((Date.now() - d.getTime()) / 86400000);
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  if (diff < 7)  return `${diff}d ago`;
  return d.toLocaleDateString('en', { month: 'short', day: 'numeric' });
}

// ─── Create modal ─────────────────────────────────────────────────────────────

function CreateModal({ onClose, onCreate }: {
  onClose: () => void;
  onCreate: (ss: StudySetSummary) => void;
}) {
  const { user, token, sessionId } = useSessionStore();
  const [title,   setTitle]   = useState('');
  const [subject, setSubject] = useState('');
  const [desc,    setDesc]    = useState('');
  const [saving,  setSaving]  = useState(false);
  const [err,     setErr]     = useState('');

  async function handleCreate() {
    if (!title.trim()) { setErr('Please enter a title'); return; }
    setSaving(true); setErr('');
    try {
      const ss = await createStudySet({
        title: title.trim(),
        subject: subject || undefined,
        description: desc.trim() || undefined,
        user_id:    user?.id,
        session_id: !user?.id ? sessionId ?? undefined : undefined,
      }, token ?? undefined);
      onCreate(ss);
    } catch (e: any) {
      setErr(e.message || 'Failed to create study set');
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl w-full max-w-md shadow-2xl">

        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--bd)]">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-indigo-500/20 flex items-center justify-center">
              <Brain size={13} className="text-indigo-400" />
            </div>
            <h2 className="text-[var(--tx1)] font-semibold text-sm">New Study Set</h2>
          </div>
          <button onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-[var(--tx6)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)] transition-colors">
            <X size={15} />
          </button>
        </div>

        <div className="px-5 py-5 space-y-4">
          <div>
            <label className="block text-[var(--tx5)] text-xs font-medium mb-1.5">Title *</label>
            <input
              autoFocus
              value={title}
              onChange={e => setTitle(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleCreate(); }}
              placeholder="e.g. Thermodynamics Chapter 3"
              className="w-full px-3 py-2.5 rounded-xl bg-[var(--ov2)] border border-[var(--bd)]
                         text-[var(--tx1)] text-sm placeholder-[var(--tx7)]
                         focus:outline-none focus:border-indigo-500/50 transition-colors"
            />
          </div>
          <div>
            <label className="block text-[var(--tx5)] text-xs font-medium mb-1.5">Subject</label>
            <select
              value={subject}
              onChange={e => setSubject(e.target.value)}
              className="w-full px-3 py-2.5 rounded-xl bg-[var(--ov2)] border border-[var(--bd)]
                         text-[var(--tx2)] text-sm focus:outline-none focus:border-indigo-500/50 transition-colors"
            >
              <option value="">Select subject…</option>
              {SUBJECT_OPTS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[var(--tx5)] text-xs font-medium mb-1.5">Description <span className="text-[var(--tx7)]">(optional)</span></label>
            <textarea
              value={desc}
              onChange={e => setDesc(e.target.value)}
              rows={2}
              placeholder="What will you be studying?"
              className="w-full px-3 py-2.5 rounded-xl bg-[var(--ov2)] border border-[var(--bd)]
                         text-[var(--tx1)] text-sm placeholder-[var(--tx7)] resize-none
                         focus:outline-none focus:border-indigo-500/50 transition-colors"
            />
          </div>
          {err && <p className="text-red-400 text-xs">{err}</p>}
        </div>

        <div className="px-5 pb-5 flex gap-2.5 justify-end">
          <button onClick={onClose}
            className="px-4 py-2 text-sm rounded-xl bg-[var(--ov3)] hover:bg-[var(--ov4)] text-[var(--tx2)] transition-colors">
            Cancel
          </button>
          <button onClick={handleCreate} disabled={saving}
            className="flex items-center gap-2 px-4 py-2 text-sm rounded-xl
                       bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50
                       text-white font-medium transition-colors">
            {saving ? <Loader size={13} className="animate-spin" /> : <Plus size={13} />}
            Create & Upload PDF
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Study set card ───────────────────────────────────────────────────────────

function StudySetCard({ ss, onDelete }: {
  ss: StudySetSummary;
  onDelete: (id: string) => void;
}) {
  const router = useRouter();

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => router.push(`/study/${ss.id}`)}
      onKeyDown={e => { if (e.key === 'Enter') router.push(`/study/${ss.id}`); }}
      className="group bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-4
                 cursor-pointer hover:border-indigo-500/30 hover:shadow-lg hover:shadow-indigo-500/5
                 transition-all duration-200 flex flex-col gap-3"
    >
      {/* Icon + subject */}
      <div className="flex items-start justify-between gap-2">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600
                        flex items-center justify-center shrink-0 shadow-sm">
          <BookOpen size={18} className="text-white" />
        </div>
        <button
          onClick={e => { e.stopPropagation(); onDelete(ss.id); }}
          className="w-7 h-7 flex items-center justify-center rounded-lg
                     text-[var(--tx7)] hover:text-red-400 hover:bg-red-500/10
                     opacity-0 group-hover:opacity-100 transition-all"
          title="Delete"
        >
          <Trash2 size={13} />
        </button>
      </div>

      {/* Title + subject */}
      <div className="flex-1 min-w-0">
        <p className="text-[var(--tx1)] font-semibold text-sm line-clamp-2 leading-snug mb-1">
          {ss.title}
        </p>
        {ss.subject && (
          <span className="text-[10px] text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-full font-medium">
            {ss.subject}
          </span>
        )}
      </div>

      {/* Stats row */}
      <div className="flex items-center gap-3 text-[var(--tx6)] text-xs">
        {ss.status === 'ready' ? (
          <>
            <span className="flex items-center gap-1">
              <Brain size={11} /> {ss.concept_count} concepts
            </span>
            <span className="flex items-center gap-1">
              <LayoutGrid size={11} /> {ss.flashcard_count} cards
            </span>
          </>
        ) : (
          <span className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium
                            ${STATUS_STYLE[ss.status] ?? STATUS_STYLE.empty}`}>
            {ss.status === 'processing' && <Loader size={10} className="animate-spin" />}
            {STATUS_LABEL[ss.status] ?? ss.status}
          </span>
        )}
        <span className="ml-auto">{formatDate(ss.created_at)}</span>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function StudyPage() {
  const router                      = useRouter();
  const { user, token, sessionId }  = useSessionStore();
  const [sets,     setSets]         = useState<StudySetSummary[]>([]);
  const [loading,  setLoading]      = useState(true);
  const [showModal, setShowModal]   = useState(false);

  useEffect(() => {
    setLoading(true);
    listStudySets(user?.id || undefined, sessionId || undefined, token || undefined)
      .then(r => { setSets(r); setLoading(false); })
      .catch(()  => setLoading(false));
  }, [user?.id, sessionId]);

  function handleCreated(ss: StudySetSummary) {
    setShowModal(false);
    // Navigate straight to the detail page to upload the PDF
    router.push(`/study/${ss.id}`);
  }

  async function handleDelete(id: string) {
    if (!confirm('Delete this study set? This cannot be undone.')) return;
    await deleteStudySet(id, token ?? undefined).catch(() => {});
    setSets(prev => prev.filter(s => s.id !== id));
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
      <Sidebar onNewChat={() => router.push('/')} />

      <main className="flex-1 flex flex-col min-w-0 overflow-hidden pt-14 md:pt-0">

        {/* Header */}
        <div className="flex items-center justify-between px-5 sm:px-6 py-4
                        border-b border-[var(--bd)] shrink-0">
          <div className="flex items-center gap-2">
            <h1 className="text-[var(--tx1)] font-semibold">Study Sets</h1>
            {!loading && sets.length > 0 && (
              <span className="px-2 py-0.5 bg-[var(--ov3)] rounded-full text-[var(--tx5)] text-xs">
                {sets.length}
              </span>
            )}
          </div>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl
                       bg-indigo-600 hover:bg-indigo-500 text-white text-sm
                       font-medium transition-colors"
          >
            <Plus size={14} /> New Study Set
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 chat-scroll px-4 sm:px-6 py-5">
          {loading ? (
            <div className="flex items-center justify-center h-40">
              <Loader size={22} className="text-[var(--tx5)] animate-spin" />
            </div>
          ) : sets.length === 0 ? (
            /* Empty state */
            <div className="flex flex-col items-center justify-center gap-5 py-20 text-center">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-600 to-purple-600
                              flex items-center justify-center shadow-lg shadow-indigo-500/20">
                <BookOpen size={28} className="text-white" />
              </div>
              <div>
                <h2 className="text-[var(--tx1)] font-semibold text-base mb-1">No study sets yet</h2>
                <p className="text-[var(--tx5)] text-sm max-w-xs leading-relaxed">
                  Upload a PDF, textbook chapter, or notes and AI will extract key concepts and flashcards automatically.
                </p>
              </div>
              <button
                onClick={() => setShowModal(true)}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl
                           bg-indigo-600 hover:bg-indigo-500 text-white text-sm
                           font-medium transition-colors"
              >
                <Upload size={15} /> Upload your first PDF
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {sets.map(ss => (
                <StudySetCard key={ss.id} ss={ss} onDelete={handleDelete} />
              ))}
            </div>
          )}
        </div>
      </main>

      {showModal && (
        <CreateModal onClose={() => setShowModal(false)} onCreate={handleCreated} />
      )}
    </div>
  );
}
