'use client';
import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import ReactMarkdown from 'react-markdown';
import {
  ArrowLeft, Upload, Loader, LayoutGrid, MessageSquare,
  ChevronLeft, ChevronRight, CheckCircle, RefreshCw,
  FileText, AlertCircle, Send, BookOpen, HelpCircle,
  Lightbulb, Repeat2, Video, Clock, Plus, Eye,
} from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { useSessionStore } from '@/store/sessionStore';
import { VideoStatusCard } from '@/components/chat/MessageBubble';
import {
  getStudySet, uploadStudyMaterial, chatWithStudySet, reviewStudyCard,
  generateQuiz, generateVideo, getStudySetConversations, getMessages,
  getConversationVideos, fetchMaterialPdf,
  StudySetDetail, StudyFlashcard, StudySetConversation, StudyMaterial, StudyConcept,
} from '@/lib/api';

// PDFViewerModal uses browser-only APIs — never SSR
const PDFViewerModal = dynamic(
  () => import('@/components/chat/PDFViewerModal').then(m => m.PDFViewerModal),
  { ssr: false, loading: () => null },
);

// ─── Types ────────────────────────────────────────────────────────────────────

type Tab = 'overview' | 'concepts' | 'flashcards' | 'chat';
type ChatView = 'list' | 'active';

type ChatMsg = {
  role:     'user' | 'assistant';
  content:  string;
  chips?:   string[];
  videoId?: number;
};

type ChatSeed = {
  concept?: string;          // concept name
  pdfQuestion?: string;      // question from PDF selection
  pdfContext?: { text?: string; imageDataUrl?: string };
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatDate(iso: string) {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  if (diff < 7)  return `${diff}d ago`;
  return new Date(iso).toLocaleDateString('en', { month: 'short', day: 'numeric' });
}

// ─── ProcessingBanner ─────────────────────────────────────────────────────────

function ProcessingBanner({ status }: { status: string }) {
  if (status === 'ready') return null;
  const cfg = {
    empty:      { cls: 'border-[var(--bd)] bg-[var(--ov2)]',   icon: <Upload size={15} className="text-[var(--tx5)]" />,            msg: 'Upload a PDF below to get started.' },
    processing: { cls: 'border-yellow-500/30 bg-yellow-500/5', icon: <Loader size={15} className="text-yellow-400 animate-spin" />, msg: 'Extracting concepts and generating flashcards — ~30–60 seconds…' },
    failed:     { cls: 'border-red-500/30 bg-red-500/5',       icon: <AlertCircle size={15} className="text-red-400" />,            msg: 'Processing failed. Try uploading again.' },
  }[status] ?? { cls: 'border-[var(--bd)] bg-[var(--ov2)]', icon: null, msg: '' };
  return (
    <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border mb-5 ${cfg.cls}`}>
      {cfg.icon}<p className="text-[var(--tx4)] text-sm">{cfg.msg}</p>
    </div>
  );
}

// ─── UploadZone ───────────────────────────────────────────────────────────────

function UploadZone({ studySetId, onUploaded }: { studySetId: string; onUploaded: () => void }) {
  const { user, token } = useSessionStore();
  const inputRef        = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [err, setErr]             = useState('');

  async function handleFile(file: File) {
    if (!file.name.toLowerCase().endsWith('.pdf')) { setErr('Only PDF files supported'); return; }
    setUploading(true); setErr('');
    try {
      await uploadStudyMaterial(studySetId, file, user?.id, token ?? undefined);
      onUploaded();
    } catch (e: any) { setErr(e.message || 'Upload failed'); setUploading(false); }
  }

  return (
    <div>
      <div
        onClick={() => !uploading && inputRef.current?.click()}
        onDragOver={e => e.preventDefault()}
        onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
        className={`border-2 border-dashed rounded-2xl p-10 text-center transition-colors
          ${uploading ? 'border-indigo-500/40 bg-indigo-500/5'
                      : 'border-[var(--bd)] hover:border-indigo-500/40 hover:bg-indigo-500/5 cursor-pointer'}`}
      >
        {uploading ? (
          <div className="flex flex-col items-center gap-3">
            <Loader size={28} className="text-indigo-400 animate-spin" />
            <p className="text-[var(--tx4)] text-sm">Uploading…</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
              <Upload size={22} className="text-indigo-400" />
            </div>
            <div>
              <p className="text-[var(--tx1)] font-medium text-sm">Drop your PDF here</p>
              <p className="text-[var(--tx6)] text-xs mt-1">or click to browse · max 50 MB</p>
            </div>
          </div>
        )}
      </div>
      {err && <p className="text-red-400 text-xs mt-2">{err}</p>}
      <input ref={inputRef} type="file" accept=".pdf,application/pdf" className="hidden"
        onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
    </div>
  );
}

// ─── OverviewTab ─────────────────────────────────────────────────────────────

function OverviewTab({
  ss, onRefresh, onOpenPdf,
}: {
  ss: StudySetDetail;
  onRefresh: () => void;
  onOpenPdf: (mat: StudyMaterial) => void;
}) {
  return (
    <div className="space-y-6">
      <ProcessingBanner status={ss.status} />

      {/* Summary */}
      {ss.summary && (
        <div className="rounded-2xl bg-[var(--surface)] border border-[var(--bd)] p-5">
          <p className="text-[var(--tx5)] text-[11px] font-semibold uppercase tracking-wide mb-2">Summary</p>
          <p className="text-[var(--tx2)] text-sm leading-relaxed">{ss.summary}</p>
        </div>
      )}

      {/* Upload */}
      {(ss.status === 'empty' || ss.status === 'failed') && (
        <UploadZone studySetId={ss.id} onUploaded={onRefresh} />
      )}

      {/* Materials */}
      {ss.materials.length > 0 && (
        <div className="space-y-2">
          <p className="text-[var(--tx5)] text-[11px] font-semibold uppercase tracking-wide">Materials</p>
          {ss.materials.map(m => (
            <div key={m.id}
              className="flex items-center gap-3 px-4 py-3 rounded-xl bg-[var(--surface)] border border-[var(--bd)]">
              <FileText size={14} className="text-indigo-400 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-[var(--tx2)] text-sm truncate">{m.filename}</p>
                {m.page_count && (
                  <p className="text-[var(--tx6)] text-xs">{m.page_count} pages · {Math.round((m.char_count || 0) / 1000)}k chars</p>
                )}
              </div>
              <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium shrink-0
                ${m.status === 'ready'      ? 'bg-emerald-500/10 text-emerald-400' :
                  m.status === 'processing' ? 'bg-yellow-500/10 text-yellow-400'   :
                  m.status === 'failed'     ? 'bg-red-500/10 text-red-400'         :
                                             'bg-[var(--ov3)] text-[var(--tx6)]'}`}>
                {m.status}
              </span>
              {/* Open PDF button — only when ready and file_url is set */}
              {m.status === 'ready' && m.file_url && (
                <button
                  onClick={() => onOpenPdf(m)}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium shrink-0
                             bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 border border-indigo-500/20
                             transition-colors"
                >
                  <Eye size={12} /> Open PDF
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Empty concept hint */}
      {ss.status === 'ready' && ss.concepts.length > 0 && (
        <div className="rounded-2xl bg-indigo-500/5 border border-indigo-500/15 px-5 py-4 flex items-center gap-3">
          <BookOpen size={16} className="text-indigo-400 shrink-0" />
          <p className="text-[var(--tx4)] text-sm">
            {ss.concepts.length} key concepts extracted — go to the <strong>Concepts</strong> tab to study them.
          </p>
        </div>
      )}
    </div>
  );
}

// ─── ConceptCard ──────────────────────────────────────────────────────────────

const CONCEPT_GRADIENTS = [
  'from-indigo-500 to-violet-500',
  'from-violet-500 to-purple-500',
  'from-blue-500 to-indigo-500',
  'from-cyan-500 to-blue-500',
  'from-teal-500 to-cyan-500',
  'from-emerald-500 to-teal-500',
  'from-purple-500 to-pink-500',
  'from-rose-500 to-pink-500',
];

function ConceptCard({
  concept, index, prevConv, convsLoading, onNewChat, onContinue,
}: {
  concept: StudyConcept;
  index: number;
  prevConv: StudySetConversation | undefined;
  convsLoading: boolean;
  onNewChat: (name: string) => void;
  onContinue: (conv: StudySetConversation) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const gradient = CONCEPT_GRADIENTS[index % CONCEPT_GRADIENTS.length];
  const hasExtra = !!(concept.explanation && concept.explanation.trim());

  return (
    <div className="group relative bg-[var(--surface)] border border-[var(--bd)] rounded-2xl
                    overflow-hidden flex flex-col
                    hover:border-indigo-500/30 hover:shadow-[0_0_0_1px_rgba(99,102,241,0.15)]
                    transition-all duration-200">
      {/* Top accent bar */}
      <div className={`h-1 w-full bg-gradient-to-r ${gradient} opacity-80`} />

      {/* Card body */}
      <div className="flex flex-col gap-3 p-4 flex-1">
        {/* Number + name */}
        <div className="flex items-start gap-3">
          <span className={`w-8 h-8 rounded-xl bg-gradient-to-br ${gradient} text-white
                            text-xs font-bold flex items-center justify-center shrink-0 shadow-sm`}>
            {index + 1}
          </span>
          <p className="text-[var(--tx1)] font-semibold text-sm leading-snug pt-1">{concept.name}</p>
        </div>

        {/* Definition */}
        <p className={`text-[var(--tx4)] text-sm leading-relaxed
                       ${!expanded && hasExtra ? 'line-clamp-3' : ''}`}>
          {concept.definition}
        </p>

        {/* Explanation (shown when expanded) */}
        {expanded && hasExtra && (
          <p className="text-[var(--tx5)] text-xs leading-relaxed border-t border-[var(--bd)] pt-3">
            {concept.explanation}
          </p>
        )}

        {/* Expand toggle */}
        {hasExtra && (
          <button
            onClick={() => setExpanded(e => !e)}
            className="self-start text-[10px] font-medium text-indigo-400 hover:text-indigo-300
                       transition-colors flex items-center gap-1">
            {expanded ? <><ChevronLeft size={11} className="rotate-90" /> Less</> : <><ChevronRight size={11} className="-rotate-90" /> More</>}
          </button>
        )}
      </div>

      {/* Action row */}
      <div className="flex gap-2 px-4 pb-4 pt-1">
        {prevConv && !convsLoading ? (
          <>
            <button
              onClick={() => onContinue(prevConv)}
              className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl
                         text-xs font-medium border transition-colors
                         bg-[var(--ov3)] hover:bg-[var(--ov4)] text-[var(--tx3)] border-[var(--bd)]">
              <MessageSquare size={11} /> Continue
            </button>
            <button
              onClick={() => onNewChat(concept.name)}
              className="w-9 h-9 flex items-center justify-center rounded-xl border transition-colors shrink-0
                         bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 border-indigo-500/20"
              title="New chat">
              <Plus size={13} />
            </button>
          </>
        ) : (
          <button
            onClick={() => onNewChat(concept.name)}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl
                       text-xs font-medium border transition-colors
                       bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 border-indigo-500/20">
            <Plus size={11} /> Chat about this
          </button>
        )}
      </div>
    </div>
  );
}

// ─── ConceptsTab ──────────────────────────────────────────────────────────────

function ConceptsTab({
  ss, convs, convsLoading, onNewChat, onContinue,
}: {
  ss: StudySetDetail;
  convs: StudySetConversation[];
  convsLoading: boolean;
  onNewChat: (conceptName: string) => void;
  onContinue: (conv: StudySetConversation) => void;
}) {
  if (ss.concepts.length === 0) return (
    <div className="flex flex-col items-center justify-center py-20 text-center gap-3">
      <BookOpen size={32} className="text-[var(--tx6)]" />
      <p className="text-[var(--tx4)] text-sm">
        {ss.status === 'ready' ? 'No concepts extracted.' : 'Upload a PDF to extract key concepts.'}
      </p>
    </div>
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="text-[var(--tx5)] text-[11px] font-semibold uppercase tracking-wide">
          Key Concepts
        </p>
        <span className="text-[var(--tx6)] text-xs bg-[var(--ov3)] border border-[var(--bd)]
                         px-2 py-0.5 rounded-full">
          {ss.concepts.length}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {ss.concepts.map((c, i) => (
          <ConceptCard
            key={c.id}
            concept={c}
            index={i}
            prevConv={convsLoading ? undefined : convs.find(cv => cv.title.startsWith(c.name))}
            convsLoading={convsLoading}
            onNewChat={onNewChat}
            onContinue={onContinue}
          />
        ))}
      </div>
    </div>
  );
}

// ─── FlashcardsTab ────────────────────────────────────────────────────────────

function FlashcardsTab({ ss }: { ss: StudySetDetail }) {
  const { user, token } = useSessionStore();
  const cards = ss.flashcards;
  const [idx, setIdx]           = useState(0);
  const [flipped, setFlipped]   = useState(false);
  const [done, setDone]         = useState<Set<number>>(new Set());
  const [again, setAgain]       = useState<number[]>([]);
  const [finished, setFinished] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const card = cards[idx] as StudyFlashcard | undefined;
  const progress = Math.round((done.size / cards.length) * 100);

  async function recordReview(rating: 1 | 4) {
    if (!card || !user?.id) return;
    setSubmitting(true);
    await reviewStudyCard(ss.id, card.id, user.id, rating, token ?? undefined).catch(() => {});
    setSubmitting(false);
  }
  async function handleGotIt()  { await recordReview(4); setDone(p => new Set([...p, idx])); advance(); }
  async function handleAgain()  { await recordReview(1); setAgain(p => [...p, idx]);         advance(); }
  function advance() { setFlipped(false); const n = idx + 1; n >= cards.length ? setFinished(true) : setIdx(n); }
  function restart() { setIdx(0); setFlipped(false); setDone(new Set()); setAgain([]); setFinished(false); }

  if (!cards.length) return (
    <div className="flex flex-col items-center justify-center py-20 text-center gap-3">
      <LayoutGrid size={32} className="text-[var(--tx6)]" />
      <p className="text-[var(--tx4)] text-sm">No flashcards yet — upload a PDF first.</p>
    </div>
  );

  if (finished) return (
    <div className="flex flex-col items-center justify-center py-16 gap-6 text-center">
      <div className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
        <CheckCircle size={30} className="text-emerald-400" />
      </div>
      <div>
        <h3 className="text-[var(--tx1)] font-semibold text-lg mb-1">Session complete!</h3>
        <p className="text-[var(--tx5)] text-sm">
          Got it: <span className="text-emerald-400 font-medium">{done.size}</span> ·
          Review again: <span className="text-amber-400 font-medium">{again.length}</span>
        </p>
      </div>
      <button onClick={restart}
        className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors">
        <RefreshCw size={14} /> Study again
      </button>
    </div>
  );

  return (
    <div className="flex flex-col items-center gap-6 max-w-xl mx-auto">
      <div className="w-full">
        <div className="flex justify-between text-xs text-[var(--tx6)] mb-1.5">
          <span>{idx + 1} / {cards.length}</span>
          <span>{progress}% done</span>
        </div>
        <div className="h-1.5 rounded-full bg-[var(--ov3)] overflow-hidden">
          <div className="h-full rounded-full bg-indigo-500 transition-all" style={{ width: `${progress}%` }} />
        </div>
      </div>
      <div onClick={() => setFlipped(f => !f)}
        className="w-full min-h-[220px] rounded-2xl border border-[var(--bd)] bg-[var(--surface)]
                   cursor-pointer select-none flex flex-col items-center justify-center p-8 text-center gap-3
                   hover:border-indigo-500/30 transition-colors">
        <span className="text-[10px] text-[var(--tx6)] uppercase tracking-widest font-medium">
          {flipped ? 'Answer' : 'Question — click to reveal'}
        </span>
        <p className={`text-[var(--tx1)] leading-relaxed ${flipped ? 'text-base' : 'text-lg font-medium'}`}>
          {flipped ? card?.back : card?.front}
        </p>
      </div>
      {flipped ? (
        <div className="flex gap-3 w-full">
          <button onClick={handleAgain} disabled={submitting}
            className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl
                       bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20
                       text-amber-400 text-sm font-medium transition-colors disabled:opacity-50">
            <RefreshCw size={14} /> Review again
          </button>
          <button onClick={handleGotIt} disabled={submitting}
            className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl
                       bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20
                       text-emerald-400 text-sm font-medium transition-colors disabled:opacity-50">
            <CheckCircle size={14} /> Got it
          </button>
        </div>
      ) : (
        <button onClick={() => setFlipped(true)}
          className="px-8 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors">
          Reveal answer
        </button>
      )}
      <div className="flex items-center gap-4">
        <button onClick={() => { setIdx(i => Math.max(0, i - 1)); setFlipped(false); }} disabled={idx === 0}
          className="w-9 h-9 flex items-center justify-center rounded-xl border border-[var(--bd)]
                     text-[var(--tx5)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)]
                     disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
          <ChevronLeft size={16} />
        </button>
        <span className="text-[var(--tx6)] text-xs">navigate</span>
        <button onClick={() => { setIdx(i => Math.min(cards.length - 1, i + 1)); setFlipped(false); }} disabled={idx === cards.length - 1}
          className="w-9 h-9 flex items-center justify-center rounded-xl border border-[var(--bd)]
                     text-[var(--tx5)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)]
                     disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}

// ─── Chips ────────────────────────────────────────────────────────────────────

const CHIP_ICONS: Record<string, React.ReactNode> = {
  'Quiz me on this':    <HelpCircle size={12} />,
  'Create a video':     <Video size={12} />,
  'Give me an example': <Lightbulb size={12} />,
  'Explain differently':<Repeat2 size={12} />,
};

function Chips({ chips, onChip }: { chips: string[]; onChip: (c: string) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {chips.map(c => (
        <button key={c} onClick={() => onChip(c)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium
                     bg-[var(--ov3)] hover:bg-indigo-500/15 hover:text-indigo-400
                     border border-[var(--bd)] hover:border-indigo-500/30
                     text-[var(--tx4)] transition-all">
          {CHIP_ICONS[c] ?? null}{c}
        </button>
      ))}
    </div>
  );
}

// ─── ActiveChat ───────────────────────────────────────────────────────────────

function ActiveChat({
  ss, seed, loadConversation, onBack,
}: {
  ss: StudySetDetail;
  seed: ChatSeed | null;
  loadConversation: StudySetConversation | null;
  onBack: () => void;
}) {
  const { user, token, sessionId } = useSessionStore();
  const router                     = useRouter();
  const [messages, setMessages]    = useState<ChatMsg[]>([]);
  const [input, setInput]          = useState('');
  const [loading, setLoading]      = useState(false);
  const [histLoading, setHistLoading] = useState(false);
  const [quizzing, setQuizzing]    = useState(false);
  const [videoing, setVideoing]    = useState(false);
  const [convId, setConvId]        = useState<string | null>(null);
  const [lastMsgId, setLastMsgId]  = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const firedRef  = useRef(false);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, loading]);

  // Load saved conversation
  useEffect(() => {
    if (!loadConversation) return;
    firedRef.current = true;
    setConvId(loadConversation.id);
    setHistLoading(true);
    Promise.all([
      getMessages(loadConversation.id, token ?? undefined),
      getConversationVideos(loadConversation.id, token ?? undefined).catch(() => []),
    ]).then(([rows, videos]) => {
      const vidMap: Record<string, number> = {};
      for (const v of videos) { if (v.message_id) vidMap[String(v.message_id)] = v.id; }

      const loaded: ChatMsg[] = rows.map(r => ({
        role:    r.role as 'user' | 'assistant',
        content: r.content,
        videoId: vidMap[String(r.id)],
      }));
      // Chips on last assistant message
      const lastAi = loaded.map((m, i) => m.role === 'assistant' ? i : -1).filter(i => i !== -1).slice(-1)[0];
      if (lastAi !== undefined && lastAi >= 0) {
        loaded[lastAi] = { ...loaded[lastAi], chips: ['Quiz me on this', 'Create a video', 'Give me an example', 'Explain differently'] };
      }
      setMessages(loaded);
    }).catch(() => {}).finally(() => setHistLoading(false));
  }, [loadConversation?.id]);

  // Auto-fire seed message
  useEffect(() => {
    if (!seed || firedRef.current || ss.status !== 'ready') return;
    firedRef.current = true;

    if (seed.pdfQuestion) {
      // PDF-based question: combine question + selected context
      const userText = seed.pdfContext?.text
        ? `${seed.pdfQuestion}\n\n---\n*Selected from PDF:*\n"${seed.pdfContext.text}"`
        : seed.pdfQuestion;
      fireMessage(userText, undefined);
    } else if (seed.concept) {
      fireMessage(`Tell me about "${seed.concept}"`, seed.concept);
    }
  }, [seed, ss.status]);

  const notReady = ss.status !== 'ready';

  async function fireMessage(text: string, conceptName?: string) {
    if (loading || notReady) return;
    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setLoading(true);
    try {
      const history = messages.slice(-10).map(m => ({ role: m.role, content: m.content }));
      const res = await chatWithStudySet(
        ss.id, text, history, token ?? undefined,
        conceptName, convId ?? undefined,
        user?.id, sessionId || undefined,
      );
      setConvId(res.conversation_id);
      setLastMsgId(res.message_id);
      setMessages(prev => [...prev, { role: 'assistant', content: res.reply, chips: res.chips }]);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Something went wrong. Please try again.' }]);
    } finally { setLoading(false); }
  }

  async function send() {
    const text = input.trim(); if (!text) return;
    setInput(''); await fireMessage(text);
  }

  function currentTopic() {
    return seed?.concept
      || messages.filter(m => m.role === 'user').slice(-1)[0]?.content?.slice(0, 120)
      || ss.title;
  }

  async function handleChip(chip: string) {
    if (chip === 'Quiz me on this') {
      setQuizzing(true);
      try {
        const res = await generateQuiz({ topic: currentTopic(), conversation_id: convId ?? undefined, user_id: user?.id, subject: ss.subject || undefined }, token ?? undefined);
        router.push(`/quiz/${res.quiz_id}`);
      } catch { setQuizzing(false); }
      return;
    }
    if (chip === 'Create a video') {
      setVideoing(true);
      try {
        const res = await generateVideo({ prompt: currentTopic(), conversation_id: convId ?? undefined, message_id: lastMsgId ?? undefined, user_id: user?.id, subject: ss.subject || undefined }, token ?? undefined);
        if (res.supported && res.video_id) {
          setMessages(prev => {
            const up = [...prev];
            for (let i = up.length - 1; i >= 0; i--) {
              if (up[i].role === 'assistant') { up[i] = { ...up[i], videoId: res.video_id! }; break; }
            }
            return up;
          });
        }
      } finally { setVideoing(false); }
      return;
    }
    await fireMessage(chip);
  }

  function chatTitle() {
    if (loadConversation?.title) return loadConversation.title;
    if (seed?.concept) return seed.concept;
    if (seed?.pdfContext?.text) {
      const snippet = seed.pdfContext.text.length > 80
        ? seed.pdfContext.text.slice(0, 80) + '…'
        : seed.pdfContext.text;
      return `📄 "${snippet}"`;
    }
    if (seed?.pdfQuestion) {
      const q = seed.pdfQuestion.length > 80 ? seed.pdfQuestion.slice(0, 80) + '…' : seed.pdfQuestion;
      return `📄 ${q}`;
    }
    return 'New chat';
  }
  const title = chatTitle();

  return (
    <div className="flex flex-col h-full">
      {/* Sub-header */}
      <div className="flex items-center gap-2 pb-3 mb-3 border-b border-[var(--bd)] shrink-0">
        <button onClick={onBack}
          className="w-7 h-7 flex items-center justify-center rounded-lg
                     text-[var(--tx5)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)] transition-colors">
          <ChevronLeft size={16} />
        </button>
        <p className="text-[var(--tx2)] text-sm font-medium truncate flex-1">{title}</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto no-scrollbar space-y-4 pb-4">
        {histLoading && (
          <div className="flex items-center justify-center py-10 gap-2 text-[var(--tx6)] text-sm">
            <Loader size={16} className="animate-spin" /> Loading…
          </div>
        )}
        {!histLoading && messages.length === 0 && !notReady && (
          <div className="flex flex-col items-center justify-center py-12 gap-3 text-center">
            <MessageSquare size={28} className="text-[var(--tx6)]" />
            <p className="text-[var(--tx5)] text-sm">Ask anything about "{ss.title}"</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
            <div className={`max-w-[88%] px-4 py-3 rounded-2xl text-sm leading-relaxed
              ${m.role === 'user'
                ? 'bg-indigo-600 text-white rounded-br-md'
                : 'bg-[var(--surface)] border border-[var(--bd)] text-[var(--tx2)] rounded-bl-md'}`}>
              {m.role === 'assistant' ? <ReactMarkdown>{m.content}</ReactMarkdown> : m.content}
            </div>
            {m.role === 'assistant' && m.videoId && (
              <div className="max-w-[88%] w-full mt-2">
                <VideoStatusCard videoId={m.videoId} token={token ?? undefined} />
              </div>
            )}
            {m.role === 'assistant' && m.chips && i === messages.length - 1 && !loading && (
              <div className="max-w-[88%] mt-1">
                {(quizzing || videoing) ? (
                  <div className="flex items-center gap-1.5 text-xs text-[var(--tx6)] py-1">
                    <Loader size={11} className="animate-spin" />
                    {quizzing ? 'Generating quiz…' : 'Generating video…'}
                  </div>
                ) : (
                  <Chips
                    chips={m.videoId ? m.chips.filter(c => c !== 'Create a video') : m.chips}
                    onChip={handleChip}
                  />
                )}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="px-4 py-3 rounded-2xl rounded-bl-md bg-[var(--surface)] border border-[var(--bd)]">
              <Loader size={14} className="text-[var(--tx5)] animate-spin" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex gap-2 pt-3 border-t border-[var(--bd)] shrink-0">
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
          disabled={notReady || loading}
          placeholder={notReady ? 'Waiting for PDF processing…' : `Ask about ${ss.title}…`}
          className="flex-1 px-4 py-2.5 rounded-xl bg-[var(--ov2)] border border-[var(--bd)]
                     text-[var(--tx1)] text-sm placeholder-[var(--tx7)]
                     focus:outline-none focus:border-indigo-500/50 disabled:opacity-50 transition-colors" />
        <button onClick={send} disabled={!input.trim() || loading || notReady}
          className="w-10 h-10 flex items-center justify-center rounded-xl
                     bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white transition-colors">
          <Send size={15} />
        </button>
      </div>
    </div>
  );
}

// ─── ChatTab ──────────────────────────────────────────────────────────────────

function ChatTab({
  ss, initSeed, initConversation,
}: {
  ss: StudySetDetail;
  initSeed: ChatSeed | null;
  initConversation: StudySetConversation | null;
}) {
  const { token } = useSessionStore();
  const [view, setView]         = useState<ChatView>(initSeed || initConversation ? 'active' : 'list');
  const [activeSeed, setActiveSeed]       = useState<ChatSeed | null>(initSeed);
  const [activeConv, setActiveConv]       = useState<StudySetConversation | null>(initConversation);
  const [convs, setConvs]       = useState<StudySetConversation[]>([]);
  const [loading, setLoading]   = useState(false);

  useEffect(() => {
    if (ss.status !== 'ready') return;
    setLoading(true);
    getStudySetConversations(ss.id, token ?? undefined)
      .then(r => { setConvs(r); setLoading(false); })
      .catch(()  => setLoading(false));
  }, [ss.id, ss.status, view]); // refresh list when returning to list view

  function startNew(seed?: ChatSeed) {
    setActiveSeed(seed ?? null);
    setActiveConv(null);
    setView('active');
  }

  function openConv(conv: StudySetConversation) {
    setActiveSeed(null);
    setActiveConv(conv);
    setView('active');
  }

  function goBack() {
    setView('list');
    setActiveSeed(null);
    setActiveConv(null);
  }

  // ── Active chat ───────────────────────────────────────────────────────────
  if (view === 'active') {
    return (
      <ActiveChat
        key={`${activeSeed?.concept ?? activeSeed?.pdfQuestion ?? 'new'}-${activeConv?.id ?? 'new'}`}
        ss={ss}
        seed={activeSeed}
        loadConversation={activeConv}
        onBack={goBack}
      />
    );
  }

  // ── Conversation list ──────────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      {/* New chat button */}
      <button onClick={() => startNew()}
        className="w-full flex items-center justify-center gap-2 py-3 rounded-2xl
                   border-2 border-dashed border-indigo-500/30 hover:border-indigo-500/50
                   text-indigo-400 hover:bg-indigo-500/5 text-sm font-medium transition-all">
        <Plus size={16} /> New chat
      </button>

      {/* Past conversations */}
      {loading ? (
        <div className="flex items-center justify-center py-8 gap-2 text-[var(--tx6)] text-sm">
          <Loader size={16} className="animate-spin" /> Loading…
        </div>
      ) : convs.length === 0 ? (
        <div className="text-center py-10 text-[var(--tx6)] text-sm">
          No conversations yet. Click "New chat" or start from a concept.
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-[var(--tx5)] text-[11px] font-semibold uppercase tracking-wide">
            History · {convs.length}
          </p>
          {convs.map(c => (
            <button key={c.id} onClick={() => openConv(c)}
              className="w-full text-left flex items-center gap-3 px-4 py-3 rounded-xl
                         bg-[var(--surface)] border border-[var(--bd)]
                         hover:border-indigo-500/30 hover:bg-indigo-500/5
                         transition-colors group">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20
                              flex items-center justify-center shrink-0">
                <MessageSquare size={13} className="text-indigo-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[var(--tx2)] text-sm font-medium truncate">{c.title}</p>
                <div className="flex items-center gap-2 mt-0.5 text-[var(--tx6)] text-xs">
                  <span className="flex items-center gap-1"><Clock size={10} />{formatDate(c.created_at)}</span>
                  {c.message_count > 0 && <span>· {c.message_count} msg</span>}
                  {c.quiz_count   > 0 && <span>· {c.quiz_count} quiz</span>}
                  {c.video_count  > 0 && <span>· {c.video_count} video</span>}
                </div>
              </div>
              <ChevronRight size={14} className="text-[var(--tx6)] opacity-0 group-hover:opacity-100 shrink-0" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function StudySetPage() {
  const params    = useParams();
  const router    = useRouter();
  const { token } = useSessionStore();
  const id        = params.id as string;

  const [ss,       setSs]       = useState<StudySetDetail | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [tab,      setTab]      = useState<Tab>('overview');

  // Chat entry state — cleared after ChatTab mounts
  const [chatSeed,     setChatSeed]     = useState<ChatSeed | null>(null);
  const [chatConv,     setChatConv]     = useState<StudySetConversation | null>(null);

  // Conversations list — shared between ConceptsTab and ChatTab list
  const [convs,        setConvs]        = useState<StudySetConversation[]>([]);
  const [convsLoading, setConvsLoading] = useState(false);

  // PDF state
  const [pdfMaterial, setPdfMaterial] = useState<StudyMaterial | null>(null);
  const [pdfFile,     setPdfFile]     = useState<File | null>(null);
  const [pdfLoading,  setPdfLoading]  = useState(false);

  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await getStudySet(id, token ?? undefined);
      setSs(data);
      if (data.status === 'processing') setTab('overview');
      return data.status;
    } catch { return 'error'; }
    finally { setLoading(false); }
  }, [id, token]);

  useEffect(() => {
    load().then(s => { if (s === 'processing') startPoll(); });
    return () => { if (pollRef.current) clearTimeout(pollRef.current); };
  }, []);

  // Load conversations when study set is ready
  useEffect(() => {
    if (!ss || ss.status !== 'ready') return;
    setConvsLoading(true);
    getStudySetConversations(ss.id, token ?? undefined)
      .then(r => { setConvs(r); setConvsLoading(false); })
      .catch(()  => setConvsLoading(false));
  }, [ss?.id, ss?.status]);

  function startPoll() {
    pollRef.current = setTimeout(async () => {
      const s = await load(); if (s === 'processing') startPoll();
    }, 4000);
  }

  function handleUploaded() { load().then(() => startPoll()); }

  // Navigate to Chat tab with a concept
  function handleNewConceptChat(conceptName: string) {
    setChatSeed({ concept: conceptName });
    setChatConv(null);
    setTab('chat');
  }

  // Navigate to Chat tab to continue a conversation
  function handleContinue(conv: StudySetConversation) {
    setChatSeed(null);
    setChatConv(conv);
    setTab('chat');
  }

  // Open PDF from material
  async function handleOpenPdf(mat: StudyMaterial) {
    setPdfLoading(true);
    setPdfMaterial(mat);
    try {
      const file = await fetchMaterialPdf(id, mat.id, mat.filename, token ?? undefined);
      setPdfFile(file);
    } catch {
      alert('Could not load PDF. Please try again.');
      setPdfMaterial(null);
    } finally { setPdfLoading(false); }
  }

  // When user asks from PDF selection
  function handlePdfAsk(question: string, context: { text?: string; imageDataUrl?: string }) {
    setPdfFile(null);
    setPdfMaterial(null);
    setChatSeed({ pdfQuestion: question, pdfContext: context });
    setChatConv(null);
    setTab('chat');
  }

  const TABS: { key: Tab; label: string; icon: React.ReactNode; disabled?: boolean }[] = [
    { key: 'overview',   label: 'Overview',   icon: <BookOpen size={13} /> },
    { key: 'concepts',   label: 'Concepts',   icon: <FileText size={13} />,   disabled: ss?.status !== 'ready' },
    { key: 'flashcards', label: 'Flashcards', icon: <LayoutGrid size={13} />, disabled: ss?.status !== 'ready' },
    { key: 'chat',       label: 'Chat',       icon: <MessageSquare size={13} />, disabled: ss?.status !== 'ready' },
  ];

  if (loading) return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
      <Sidebar onNewChat={() => router.push('/')} />
      <main className="flex-1 flex items-center justify-center">
        <Loader size={24} className="text-[var(--tx5)] animate-spin" />
      </main>
    </div>
  );

  if (!ss) return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
      <Sidebar onNewChat={() => router.push('/')} />
      <main className="flex-1 flex items-center justify-center text-[var(--tx5)]">Study set not found.</main>
    </div>
  );

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
      <Sidebar onNewChat={() => router.push('/')} />

      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 sm:px-6 py-4 border-b border-[var(--bd)] shrink-0">
          <button onClick={() => router.back()}
            className="text-[var(--tx5)] hover:text-[var(--tx1)] transition-colors">
            <ArrowLeft size={20} />
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-[var(--tx1)] font-semibold truncate">{ss.title}</h1>
            {ss.subject && <span className="text-indigo-400 text-xs">{ss.subject}</span>}
          </div>
          {ss.status === 'processing' && (
            <span className="flex items-center gap-1.5 text-xs text-yellow-400 bg-yellow-500/10
                             px-2.5 py-1 rounded-full border border-yellow-500/20 shrink-0">
              <Loader size={10} className="animate-spin" /> Processing
            </span>
          )}
          {ss.status === 'ready' && (
            <span className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-500/10
                             px-2.5 py-1 rounded-full border border-emerald-500/20 shrink-0">
              <CheckCircle size={10} /> Ready
            </span>
          )}
          {pdfLoading && (
            <span className="flex items-center gap-1.5 text-xs text-indigo-400 bg-indigo-500/10
                             px-2.5 py-1 rounded-full border border-indigo-500/20 shrink-0">
              <Loader size={10} className="animate-spin" /> Loading PDF…
            </span>
          )}
        </div>

        {/* Tabs */}
        <div className="flex border-b border-[var(--bd)] px-4 sm:px-6 shrink-0 overflow-x-auto no-scrollbar">
          {TABS.map(t => (
            <button key={t.key} onClick={() => !t.disabled && setTab(t.key)} disabled={t.disabled}
              className={`flex items-center gap-1.5 px-4 py-3 text-sm font-medium border-b-2 whitespace-nowrap
                          transition-colors disabled:opacity-30 disabled:cursor-not-allowed
                ${tab === t.key
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-[var(--tx5)] hover:text-[var(--tx2)]'}`}>
              {t.icon}{t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto no-scrollbar px-4 sm:px-6 py-6">
          {tab === 'overview' && (
            <OverviewTab ss={ss} onRefresh={handleUploaded} onOpenPdf={handleOpenPdf} />
          )}
          {tab === 'concepts' && (
            <ConceptsTab
              ss={ss} convs={convs} convsLoading={convsLoading}
              onNewChat={handleNewConceptChat} onContinue={handleContinue}
            />
          )}
          {tab === 'flashcards' && <FlashcardsTab ss={ss} />}
          {tab === 'chat' && (
            <ChatTab
              key={`${chatSeed?.concept ?? chatSeed?.pdfQuestion ?? 'general'}-${chatConv?.id ?? 'new'}`}
              ss={ss}
              initSeed={chatSeed}
              initConversation={chatConv}
            />
          )}
        </div>
      </main>

      {/* PDF Viewer Modal */}
      {pdfFile && (
        <PDFViewerModal
          file={pdfFile}
          onClose={() => { setPdfFile(null); setPdfMaterial(null); }}
          onAsk={handlePdfAsk}
        />
      )}
    </div>
  );
}
