'use client';
import { useEffect, useState, useRef, useCallback } from 'react';

function decodeHtml(s: string): string {
  if (typeof document === 'undefined') return s;
  const el = document.createElement('textarea');
  el.innerHTML = s;
  return el.value;
}
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { preprocessMath } from '@/lib/preprocessMath';
import { KATEX_OPTIONS } from '@/lib/mathConfig';
import { SmilesBlock } from '@/components/chat/SmilesBlock';
import { MathText } from '@/components/ui/MathText';
import {
  ArrowLeft, ArrowRight, Upload, Loader, LayoutGrid, MessageSquare,
  ChevronLeft, ChevronRight, CheckCircle, RefreshCw,
  FileText, AlertCircle, Send, BookOpen, HelpCircle,
  Eye, Bug,
  ZoomIn, ZoomOut, X as XIcon, ImageIcon,
} from 'lucide-react';
import { Sidebar, MobileTopBar } from '@/components/layout/Sidebar';
import { useSessionStore } from '@/store/sessionStore';
import { useLanguageStore } from '@/store/languageStore';
import { useTranslation } from '@/hooks/useTranslation';
import { VideoStatusCard } from '@/components/chat/MessageBubble';
import { DiagramsGallery } from '@/components/chat/DiagramsGallery';
import {
  getStudySet, uploadStudyMaterial, chatWithStudySet, reviewStudyCard,
  generateQuiz, generateVideo, getStudySetConversations, getMessages,
  getConversationVideos, fetchMaterialPdf, uploadRegionImage,
  getQuiz,
  createSession,
  extractStudySetConcepts,
  debugStudysetPrompt,
  StudySetDetail, StudyFlashcard, StudySetConversation, StudyMaterial, StudyConcept,
} from '@/lib/api';
import { DebugPromptModal } from '@/components/chat/DebugPromptModal';

// Browser-only components — never SSR
const PDFViewerModal = dynamic(
  () => import('@/components/chat/PDFViewerModal').then(m => m.PDFViewerModal),
  { ssr: false, loading: () => null },
);
const StudyPDFPane = dynamic(
  () => import('@/components/study/StudyPDFPane').then(m => m.StudyPDFPane),
  { ssr: false, loading: () => null },
);
import type { PinnedCtx } from '@/components/study/StudyPDFPane';

// ─── Types ────────────────────────────────────────────────────────────────────

type Tab = 'overview' | 'concepts' | 'flashcards' | 'chat' | 'diagrams';


type ChatMsg = {
  role:              'user' | 'assistant';
  content:           string;
  chips?:            string[];
  videoId?:          number;
  imageUrl?:         string;
  id?:               string;
  quizId?:           string;
  quizTopic?:        string;
  quizQuestionCount?: number;
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
  const { t } = useTranslation();
  if (status === 'ready') return null;
  const cfg = {
    empty:      { cls: 'border-[var(--bd)] bg-[var(--ov2)]',   icon: <Upload size={15} className="text-[var(--tx5)]" />,            msg: t.studySets.uploadGetStarted },
    processing: { cls: 'border-yellow-500/30 bg-yellow-500/5', icon: <Loader size={15} className="text-yellow-400 animate-spin" />, msg: t.studySets.extractingProcessing },
    failed:     { cls: 'border-red-500/30 bg-red-500/5',       icon: <AlertCircle size={15} className="text-red-400" />,            msg: t.studySets.processingFailed },
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
  const { t } = useTranslation();
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
            <p className="text-[var(--tx4)] text-sm">{t.upload.uploading}</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
              <Upload size={22} className="text-indigo-400" />
            </div>
            <div>
              <p className="text-[var(--tx1)] font-medium text-sm">{t.studySets.dropZone}</p>
              <p className="text-[var(--tx6)] text-xs mt-1">{t.studySets.dropZoneHint}</p>
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
  const { t } = useTranslation();
  return (
    <div className="space-y-6">
      <ProcessingBanner status={ss.status} />

      {/* Summary */}
      {ss.summary && (
        <div className="rounded-2xl bg-[var(--surface)] border border-[var(--bd)] p-5">
          <p className="text-[var(--tx5)] text-[11px] font-semibold uppercase tracking-wide mb-2">{t.studySets.summary}</p>
          <div className="text-[var(--tx2)] text-sm leading-relaxed [&>p]:mb-2 [&>p:last-child]:mb-0"><MathText>{ss.summary}</MathText></div>
        </div>
      )}

      {/* Upload */}
      {(ss.status === 'empty' || ss.status === 'failed') && (
        <UploadZone studySetId={ss.id} onUploaded={onRefresh} />
      )}

      {/* Materials */}
      {ss.materials.length > 0 && (
        <div className="space-y-2">
          <p className="text-[var(--tx5)] text-[11px] font-semibold uppercase tracking-wide">{t.studySets.materials}</p>
          {ss.materials.map(m => (
            <div key={m.id}>
              {m.status === 'ready' ? (
                /* Clickable PDF card */
                <button
                  onClick={() => onOpenPdf(m)}
                  className="w-full text-left group rounded-2xl bg-[var(--surface)] border border-[var(--bd)]
                             hover:border-indigo-500/35 hover:shadow-[0_0_0_1px_rgba(99,102,241,0.12)]
                             transition-all overflow-hidden">
                  {/* Gradient top bar */}
                  <div className="h-0.5 w-full bg-gradient-to-r from-indigo-500 via-violet-500 to-purple-500 opacity-60
                                  group-hover:opacity-100 transition-opacity" />
                  <div className="flex items-center gap-3 px-4 py-3.5">
                    <div className="w-9 h-9 rounded-xl bg-indigo-500/10 border border-indigo-500/20
                                    flex items-center justify-center shrink-0
                                    group-hover:bg-indigo-500/15 transition-colors">
                      <FileText size={16} className="text-indigo-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[var(--tx1)] text-sm font-medium truncate">{m.filename}</p>
                      <p className="text-[var(--tx6)] text-xs mt-0.5">
                        {m.page_count ? `${m.page_count} pages` : ''}
                        {m.page_count && m.char_count ? ' · ' : ''}
                        {m.char_count ? `${Math.round(m.char_count / 1000)}k chars` : ''}
                        {(m.page_count || m.char_count) ? ' · ' : ''}
                        <span className="text-indigo-400">{t.studySets.selectRegionHint}</span>
                      </p>
                    </div>
                    <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg shrink-0
                                    bg-indigo-500/10 group-hover:bg-indigo-500/20
                                    text-indigo-400 border border-indigo-500/20 transition-colors">
                      <Eye size={12} />
                      <span className="text-xs font-medium">{t.studySets.openPdf}</span>
                    </div>
                  </div>
                </button>
              ) : (
                /* Non-ready material row */
                <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-[var(--surface)] border border-[var(--bd)]">
                  <FileText size={14} className="text-[var(--tx6)] shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-[var(--tx2)] text-sm truncate">{m.filename}</p>
                    {m.page_count && (
                      <p className="text-[var(--tx6)] text-xs">{m.page_count} pages · {Math.round((m.char_count || 0) / 1000)}k chars</p>
                    )}
                  </div>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium shrink-0
                    ${m.status === 'processing' ? 'bg-yellow-500/10 text-yellow-400' :
                      m.status === 'failed'     ? 'bg-red-500/10 text-red-400'       :
                                                 'bg-[var(--ov3)] text-[var(--tx6)]'}`}>
                    {m.status}
                  </span>
                </div>
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
            {t.studySets.conceptsExtractedNote.replace('{n}', String(ss.concepts.length))}
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
  concept, index, onChat,
}: {
  concept: StudyConcept;
  index: number;
  onChat: (id: string) => void;
}) {
  const { t } = useTranslation();
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
          <MathText inline>{concept.definition}</MathText>
        </p>

        {/* Explanation (shown when expanded) */}
        {expanded && hasExtra && (
          <p className="text-[var(--tx5)] text-xs leading-relaxed border-t border-[var(--bd)] pt-3">
            <MathText inline>{concept.explanation}</MathText>
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
        <button
          onClick={() => onChat(concept.id)}
          className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl
                     text-xs font-medium border transition-colors
                     bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 border-indigo-500/20">
          <MessageSquare size={11} /> {t.studySets.chatAboutThis}
        </button>
      </div>
    </div>
  );
}

// ─── ConceptsTab ──────────────────────────────────────────────────────────────

function ConceptsTab({
  ss, onChat, onConceptsGenerated,
}: {
  ss: StudySetDetail;
  onChat: (conceptId: string) => void;
  onConceptsGenerated?: () => void;
}) {
  const { t } = useTranslation();
  const { token } = useSessionStore();
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);

  const hasMaterialText = ss.materials.some(m => m.status === 'ready');

  async function handleGenerate() {
    setGenerating(true);
    setGenError(null);
    try {
      await extractStudySetConcepts(ss.id, token ?? undefined);
      onConceptsGenerated?.();
    } catch (e: any) {
      setGenError(e?.message || 'Failed to generate concepts');
    } finally {
      setGenerating(false);
    }
  }

  if (ss.concepts.length === 0) return (
    <div className="flex flex-col items-center justify-center py-20 text-center gap-4">
      <BookOpen size={32} className="text-[var(--tx6)]" />
      <p className="text-[var(--tx4)] text-sm">
        {ss.status === 'ready' ? t.studySets.noConcepts : t.studySets.noConceptsUpload}
      </p>
      {ss.status === 'ready' && hasMaterialText && (
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium
                     bg-indigo-500/10 hover:bg-indigo-500/15 border border-indigo-500/30
                     text-indigo-400 hover:text-indigo-300 transition-all disabled:opacity-50">
          {generating ? <Loader size={14} className="animate-spin" /> : <BookOpen size={14} />}
          {generating ? 'Generating…' : 'Generate concepts with AI'}
        </button>
      )}
      {genError && <p className="text-red-400 text-xs">{genError}</p>}
    </div>
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="text-[var(--tx5)] text-[11px] font-semibold uppercase tracking-wide">
          {t.studySets.keyConceptsHeader}
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
            onChat={onChat}
          />
        ))}
      </div>
    </div>
  );
}

// ─── FlashcardsTab ────────────────────────────────────────────────────────────

function FlashcardsTab({ ss }: { ss: StudySetDetail }) {
  const { user, token } = useSessionStore();
  const { t } = useTranslation();
  const cards = ss.flashcards;
  const [idx, setIdx]           = useState(0);
  const [flipped, setFlipped]   = useState(false);
  const [done, setDone]         = useState<Set<number>>(new Set());
  const [again, setAgain]       = useState<number[]>([]);
  const [finished, setFinished] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const card = cards[idx] as StudyFlashcard | undefined;
  const progress = Math.round((done.size / cards.length) * 100);
  const dueCount = cards.filter(c => c.is_due).length;

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
      <p className="text-[var(--tx4)] text-sm">{t.studySets.noFlashcards}</p>
    </div>
  );

  if (finished) return (
    <div className="flex flex-col items-center justify-center py-16 gap-6 text-center">
      <div className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
        <CheckCircle size={30} className="text-emerald-400" />
      </div>
      <div>
        <h3 className="text-[var(--tx1)] font-semibold text-lg mb-1">{t.studySets.sessionComplete}</h3>
        <p className="text-[var(--tx5)] text-sm">
          {t.studySets.progress.replace('{done}', String(done.size)).replace('{again}', String(again.length))}
        </p>
      </div>
      <button onClick={restart}
        className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors">
        <RefreshCw size={14} /> {t.studySets.studyAgain}
      </button>
    </div>
  );

  return (
    <div className="flex flex-col items-center gap-6 max-w-xl mx-auto">
      <div className="w-full">
        <div className="flex justify-between text-xs text-[var(--tx6)] mb-1.5">
          <span>{idx + 1} / {cards.length}{dueCount > 0 && ` · ${dueCount} due for review`}</span>
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
          {flipped ? t.studySets.answerLabel : t.studySets.questionReveal}
        </span>
        <p className={`text-[var(--tx1)] leading-relaxed ${flipped ? 'text-base' : 'text-lg font-medium'}`}>
          <MathText inline>{(flipped ? card?.back : card?.front) ?? ''}</MathText>
        </p>
      </div>
      {flipped ? (
        <div className="flex gap-3 w-full">
          <button onClick={handleAgain} disabled={submitting}
            className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl
                       bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20
                       text-amber-400 text-sm font-medium transition-colors disabled:opacity-50">
            <RefreshCw size={14} /> {t.studySets.studyAgain}
          </button>
          <button onClick={handleGotIt} disabled={submitting}
            className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl
                       bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20
                       text-emerald-400 text-sm font-medium transition-colors disabled:opacity-50">
            <CheckCircle size={14} /> {t.studySets.knew}
          </button>
        </div>
      ) : (
        <button onClick={() => setFlipped(true)}
          className="px-8 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors">
          {t.studySets.revealAnswer}
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

// ─── ImageLightbox ────────────────────────────────────────────────────────────

function ImageLightbox({ src, onClose }: { src: string; onClose: () => void }) {
  const [zoom, setZoom] = useState(1);
  const MIN = 0.5, MAX = 5, STEP = 0.4;

  // Keyboard: Escape closes, +/- zooms
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
      if (e.key === '+' || e.key === '=') setZoom(z => Math.min(MAX, parseFloat((z + STEP).toFixed(1))));
      if (e.key === '-')                  setZoom(z => Math.max(MIN, parseFloat((z - STEP).toFixed(1))));
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Ctrl/Cmd + wheel
  useEffect(() => {
    function onWheel(e: WheelEvent) {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      setZoom(z => parseFloat(Math.min(MAX, Math.max(MIN, z + (e.deltaY < 0 ? STEP : -STEP))).toFixed(1)));
    }
    window.addEventListener('wheel', onWheel, { passive: false });
    return () => window.removeEventListener('wheel', onWheel);
  }, []);

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/90 backdrop-blur-sm"
      onClick={onClose}
    >
      {/* Controls */}
      <div
        className="absolute top-4 right-4 flex items-center gap-1.5 z-10"
        onClick={e => e.stopPropagation()}
      >
        <button
          onClick={() => setZoom(z => Math.max(MIN, parseFloat((z - STEP).toFixed(1))))}
          className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/10 hover:bg-white/20 text-white transition-colors">
          <ZoomOut size={16} />
        </button>
        <span className="text-white/50 text-xs w-12 text-center tabular-nums select-none">
          {Math.round(zoom * 100)}%
        </span>
        <button
          onClick={() => setZoom(z => Math.min(MAX, parseFloat((z + STEP).toFixed(1))))}
          className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/10 hover:bg-white/20 text-white transition-colors">
          <ZoomIn size={16} />
        </button>
        <div className="w-px h-5 bg-white/20 mx-0.5" />
        <button
          onClick={onClose}
          className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/10 hover:bg-white/20 text-white transition-colors">
          <XIcon size={16} />
        </button>
      </div>

      {/* Reset zoom on double-click */}
      <div
        className="overflow-auto max-w-full max-h-full p-4"
        style={{ cursor: zoom > 1 ? 'zoom-out' : 'zoom-in' }}
        onClick={e => { e.stopPropagation(); setZoom(z => z === 1 ? 2.5 : 1); }}
      >
        <img
          src={src}
          alt="PDF region"
          style={{ transform: `scale(${zoom})`, transformOrigin: 'center center', transition: 'transform 0.15s ease' }}
          className="max-w-[90vw] max-h-[90vh] object-contain rounded-lg select-none"
          draggable={false}
        />
      </div>

      {/* Hint */}
      <p className="absolute bottom-4 left-1/2 -translate-x-1/2 text-white/30 text-xs select-none pointer-events-none">
        Click to toggle zoom · Ctrl+scroll · Esc to close
      </p>
    </div>
  );
}

// ─── StudyQuizCard ────────────────────────────────────────────────────────────

function StudyQuizCard({
  quizId, quizTopic, quizQuestionCount, returnUrl, token,
}: {
  quizId: string;
  quizTopic?: string;
  quizQuestionCount?: number;
  returnUrl: string;
  token?: string;
}) {
  const router = useRouter();
  const [status, setStatus] = useState<{
    completed: boolean;
    score?: number;
    max_score?: number;
    score_pct?: number;
  } | null>(null);

  useEffect(() => {
    getQuiz(quizId, token)
      .then(d => {
        if (d.completed && d.score != null && d.max_score) {
          setStatus({
            completed: true,
            score: d.score,
            max_score: d.max_score,
            score_pct: Math.round((d.score / d.max_score) * 100),
          });
        } else {
          setStatus({ completed: false });
        }
      })
      .catch(() => setStatus({ completed: false }));
  }, [quizId]);

  return (
    <button
      onClick={() => router.push(`/quiz/${quizId}?from=${encodeURIComponent(returnUrl)}`)}
      className="w-full flex items-center gap-3 px-4 py-3 rounded-xl
                 bg-amber-500/10 border border-amber-500/25 hover:bg-amber-500/20
                 text-left transition-all group"
    >
      <HelpCircle size={18} className="text-amber-400 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="text-xs font-semibold text-amber-400 uppercase tracking-wide mb-0.5">Quiz</p>
        <p className="text-sm text-[var(--tx2)] truncate">
          {quizTopic || 'View quiz'}
          {quizQuestionCount ? ` · ${quizQuestionCount} questions` : ''}
        </p>
      </div>
      {status === null ? (
        <Loader size={12} className="text-amber-400/50 animate-spin shrink-0" />
      ) : status.completed && status.score_pct != null ? (
        <div className="text-right shrink-0">
          <p className="text-sm font-bold text-amber-400">{status.score_pct}%</p>
          <p className="text-[10px] text-amber-400/60">
            {status.score}/{status.max_score} · Review
          </p>
        </div>
      ) : (
        <ArrowRight size={14} className="text-amber-400/60 shrink-0 group-hover:translate-x-0.5 transition-transform" />
      )}
    </button>
  );
}

// ─── ActiveChat ───────────────────────────────────────────────────────────────

function ActiveChat({
  ss, studyConceptId, loadConversation,
  pendingFire, onFired, pinnedCtx, onClearCtx,
  onNewConversation,
}: {
  ss: StudySetDetail;
  studyConceptId?: string | null;
  loadConversation: StudySetConversation | null;
  pendingFire?: { text: string; imageDataUrl?: string } | null;
  onFired?: () => void;
  pinnedCtx?: PinnedCtx | null;
  onClearCtx?: () => void;
  onNewConversation?: (convId: string) => void;
}) {
  const { user, token, sessionId } = useSessionStore();
  const { language }               = useLanguageStore();
  const { t: tChat }               = useTranslation();
  const router                     = useRouter();
  const [messages, setMessages]    = useState<ChatMsg[]>([]);
  const [input, setInput]          = useState('');
  const [loading, setLoading]      = useState(false);
  const [histLoading, setHistLoading] = useState(false);
  const [histLoaded, setHistLoaded]   = useState(!loadConversation);
  const [quizzing, setQuizzing]    = useState(false);
  const [lightboxSrc, setLightboxSrc] = useState<string | null>(null);
  const [videoing, setVideoing]    = useState(false);
  const [convId, setConvId]        = useState<string | null>(null);
  const [lastMsgId, setLastMsgId]  = useState<string | null>(null);
  const [debugData,  setDebugData] = useState<any>(null);
  const bottomRef   = useRef<HTMLDivElement>(null);
  const firedRef    = useRef(false);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, loading]);

  // Sync new convId to URL so refresh can restore the conversation
  useEffect(() => {
    if (convId && !loadConversation) {
      window.history.replaceState({}, '', `/study/${ss.id}?tab=chat&conv=${convId}`);
    }
  }, [convId]);

  // Load saved conversation
  useEffect(() => {
    if (!loadConversation) return;
    setConvId(loadConversation.id);
    setHistLoading(true);
    Promise.all([
      getMessages(loadConversation.id, token ?? undefined),
      getConversationVideos(loadConversation.id, token ?? undefined).catch(() => []),
    ]).then(([rows, videos]) => {
      const lastAiId = [...rows].reverse().find((r: any) => r.role === 'assistant')?.id;
      const lastAiKey = lastAiId ? String(lastAiId) : null;

      const vidMap: Record<string, number> = {};
      for (const v of videos) {
        const key = v.message_id ?? lastAiKey;
        if (key) vidMap[key] = v.id;
      }
      // localStorage fallback — covers cases where conversation_id was null in DB
      if (lastAiKey && !vidMap[lastAiKey]) {
        try {
          const stored = localStorage.getItem(`learnai_video_${lastAiKey}`);
          if (stored) { const vid = Number(stored); if (vid) vidMap[lastAiKey] = vid; }
        } catch {}
      }
      // conversation-level fallback (written at generation time)
      if (lastAiKey && !vidMap[lastAiKey]) {
        try {
          const stored = localStorage.getItem(`learnai_conv_video_${loadConversation.id}`);
          if (stored) { const vid = Number(stored); if (vid) vidMap[lastAiKey] = vid; }
        } catch {}
      }

      const lastAiRowId = [...rows].reverse().find((r: any) => r.role === 'assistant')?.id;
      const loaded: ChatMsg[] = rows.map(r => ({
        role:              r.role as 'user' | 'assistant',
        content:           r.content,
        videoId:           vidMap[String(r.id)],
        imageUrl:          r.metadata?.image_url as string | undefined,
        id:                String(r.id),
        quizId:            r.metadata?.quiz_id as string | undefined,
        quizTopic:         r.metadata?.quiz_topic as string | undefined,
        quizQuestionCount: r.metadata?.num_questions as number | undefined,
        // Restore AI-generated chips on the last assistant message only
        chips: (r.role === 'assistant' && String(r.id) === String(lastAiRowId))
          ? (Array.isArray(r.metadata?.chips) ? r.metadata.chips : [])
          : undefined,
      }));
      if (lastAiRowId) setLastMsgId(String(lastAiRowId));

      setMessages(loaded);
    }).catch(() => {}).finally(() => { setHistLoading(false); setHistLoaded(true); });
  }, [loadConversation?.id]);

  // Auto-fire messages from the PDF pane (preset actions like Explain/Summarize)
  useEffect(() => {
    if (!pendingFire || loading || !histLoaded) return;
    const captured = pendingFire;
    onFired?.(); // clear parent state immediately so this effect won't re-run
    async function doPdfFire() {
      let imageUrl: string | undefined;
      if (captured.imageDataUrl) {
        try { imageUrl = await uploadRegionImage(captured.imageDataUrl, user?.id, sessionId || undefined, token ?? undefined); } catch { }
      }
      await fireMessage(captured.text, undefined, imageUrl);
    }
    doPdfFire();
  }, [pendingFire]);

  const notReady = ss.status !== 'ready';

  async function fireMessage(text: string, conceptName?: string, imageUrl?: string) {
    if (loading || notReady) return;
    setMessages(prev => [...prev, { role: 'user', content: text, imageUrl }]);
    setLoading(true);
    try {
      const history = messages.slice(-10).map(m => ({ role: m.role, content: m.content }));
      const res = await chatWithStudySet(
        ss.id, text, history, token ?? undefined,
        conceptName, convId ?? undefined,
        user?.id, sessionId || undefined,
        imageUrl, language,
        studyConceptId ?? null,
      );
      if (!convId) onNewConversation?.(res.conversation_id);
      setConvId(res.conversation_id);
      setLastMsgId(res.message_id);
      const ACTION_CHIPS = new Set(['Create a video', 'Quiz me on this']);
      const defaultChips = ['Give me an example', 'Explain differently'];
      const chips = (res.chips?.length ? res.chips : defaultChips).filter((c: string) => !ACTION_CHIPS.has(c));
      setMessages(prev => [...prev, { role: 'assistant', content: res.reply, chips, id: res.message_id }]);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Something went wrong. Please try again.' }]);
    } finally { setLoading(false); }
  }

  async function send() {
    const text = input.trim(); if (!text) return;
    setInput('');
    let imageUrl: string | undefined;
    let fullText = text;
    if (pinnedCtx) {
      if (pinnedCtx.imageDataUrl) {
        try { imageUrl = await uploadRegionImage(pinnedCtx.imageDataUrl, user?.id, sessionId || undefined, token ?? undefined); } catch { }
      }
      if (pinnedCtx.text) {
        fullText = `${text}\n\n[Page ${pinnedCtx.pageNum} content:]\n${pinnedCtx.text}`;
      }
      onClearCtx?.();
    }
    await fireMessage(fullText, undefined, imageUrl);
  }

  async function handleDebug() {
    try {
      const data = await debugStudysetPrompt(ss.id, {
        message:         input.trim() || '(empty)',
        conversation_id: convId ?? undefined,
        user_id:         user?.id,
        session_id:      sessionId || undefined,
      }, token ?? undefined);
      setDebugData(data);
    } catch (e) { console.error('Debug prompt error', e); }
  }

  function currentTopic() {
    return (studyConceptId && ss.concepts.find(c => c.id === studyConceptId)?.name)
      || messages.filter(m => m.role === 'user').slice(-1)[0]?.content?.slice(0, 120)
      || ss.title;
  }

  async function handleChip(chip: string) {
    if (chip === 'Quiz me on this') {
      setQuizzing(true);
      try {
        const topic = currentTopic();
        const res = await generateQuiz({ topic, conversation_id: convId ?? undefined, user_id: user?.id, subject: ss.subject || undefined, language }, token ?? undefined);
        if (res.message_id) {
          setMessages(prev => [...prev, {
            role: 'assistant', content: `Quiz: ${ss.subject || topic}`,
            id: res.message_id!, quizId: res.quiz_id,
            quizTopic: ss.subject || topic, quizQuestionCount: res.questions?.length,
          }]);
        }
        const returnUrl = `/study/${ss.id}?tab=chat${convId ? `&conv=${convId}` : ''}`;
        router.push(`/quiz/${res.quiz_id}?from=${encodeURIComponent(returnUrl)}`);
      } catch { setQuizzing(false); }
      return;
    }
    if (chip === 'Create a video') {
      setVideoing(true);
      try {
        const lastAiContent = [...messages].reverse().find(m => m.role === 'assistant')?.content
          ?? currentTopic();
        const res = await generateVideo({ prompt: lastAiContent.slice(0, 400), conversation_id: convId ?? undefined, message_id: lastMsgId ?? undefined, user_id: user?.id, session_id: sessionId ?? undefined, subject: ss.subject || undefined, language }, token ?? undefined);
        if (res.supported && res.video_id) {
          setMessages(prev => {
            const up = [...prev];
            for (let i = up.length - 1; i >= 0; i--) {
              if (up[i].role === 'assistant') { up[i] = { ...up[i], videoId: res.video_id! }; break; }
            }
            return up;
          });
          if (lastMsgId) {
            try { localStorage.setItem(`learnai_video_${lastMsgId}`, String(res.video_id)); } catch {}
          }
          if (convId) {
            try { localStorage.setItem(`learnai_conv_video_${convId}`, String(res.video_id)); } catch {}
          }
        }
      } finally { setVideoing(false); }
      return;
    }
    await fireMessage(chip);
  }

  // Action buttons shown under every AI message (not just the last one)
  async function handlePerMessageAction(
    action: 'Create a video' | 'Quiz me on this',
    msgContent: string,
    msgId: string | undefined,
    msgIndex: number,
  ) {
    if (action === 'Quiz me on this') {
      setQuizzing(true);
      try {
        const topic = msgContent.slice(0, 120);
        const res = await generateQuiz({
          topic,
          conversation_id: convId ?? undefined,
          user_id: user?.id,
          subject: ss.subject || undefined,
          language,
        }, token ?? undefined);
        if (res.message_id) {
          setMessages(prev => [...prev, {
            role: 'assistant', content: `Quiz: ${ss.subject || topic}`,
            id: res.message_id!, quizId: res.quiz_id,
            quizTopic: ss.subject || topic, quizQuestionCount: res.questions?.length,
          }]);
        }
        const returnUrl = `/study/${ss.id}?tab=chat${convId ? `&conv=${convId}` : ''}`;
        router.push(`/quiz/${res.quiz_id}?from=${encodeURIComponent(returnUrl)}`);
      } catch { setQuizzing(false); }
      return;
    }
    if (action === 'Create a video') {
      setVideoing(true);
      try {
        const res = await generateVideo({
          prompt: msgContent.slice(0, 400),
          conversation_id: convId ?? undefined,
          message_id: msgId ?? undefined,
          user_id: user?.id,
          session_id: sessionId ?? undefined,
          subject: ss.subject || undefined,
          language,
        }, token ?? undefined);
        if (res.supported && res.video_id) {
          setMessages(prev => prev.map((m2, j) =>
            j === msgIndex ? { ...m2, videoId: res.video_id! } : m2
          ));
          if (msgId) {
            try { localStorage.setItem(`learnai_video_${msgId}`, String(res.video_id)); } catch {}
          }
          if (convId) {
            try { localStorage.setItem(`learnai_conv_video_${convId}`, String(res.video_id)); } catch {}
          }
        } else if (!res.supported) {
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: `🎬 ${res.message || 'Video generation not available for this subject yet.'}`,
          }]);
        }
      } finally { setVideoing(false); }
      return;
    }
  }

  const chatTitle = loadConversation?.title || (studyConceptId
    ? (ss.concepts.find(c => c.id === studyConceptId)?.name ?? 'Concept Chat')
    : 'General Chat');

  return (
    <div className="flex flex-col h-full">
      {/* Sub-header */}
      <div className="flex items-center gap-2 pb-3 mb-3 border-b border-[var(--bd)] shrink-0">
        <p className="text-[var(--tx2)] text-sm font-medium truncate flex-1 min-w-0">{chatTitle}</p>
      </div>

      {/* Messages */}
      <div className="flex-1 chat-scroll space-y-4 pb-4">
        {histLoading && (
          <div className="flex items-center justify-center py-10 gap-2 text-[var(--tx6)] text-sm">
            <Loader size={16} className="animate-spin" /> {tChat.studySets.chatLoading}
          </div>
        )}
        {!histLoading && messages.length === 0 && !notReady && (
          <div className="flex flex-col items-center justify-center py-12 gap-3 text-center">
            <MessageSquare size={28} className="text-[var(--tx6)]" />
            <p className="text-[var(--tx5)] text-sm">{tChat.studySets.askAnything.replace('{title}', ss.title)}</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
            {/* PDF region thumbnail — click to open lightbox */}
            {m.role === 'user' && m.imageUrl && (
              <div className="max-w-[88%] mb-1.5">
                <div className="flex items-center gap-1.5 mb-1">
                  <FileText size={11} className="text-indigo-300" />
                  <span className="text-[10px] text-indigo-300/70 font-medium">From PDF</span>
                </div>
                <button
                  onClick={() => setLightboxSrc(m.imageUrl!)}
                  className="block group relative rounded-xl overflow-hidden border border-indigo-500/30
                             hover:border-indigo-400/60 transition-colors cursor-zoom-in">
                  <img
                    src={m.imageUrl}
                    alt="Selected PDF region"
                    className="bg-white max-w-full block"
                    style={{ maxHeight: '180px', objectFit: 'contain' }}
                  />
                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors
                                  flex items-center justify-center opacity-0 group-hover:opacity-100">
                    <div className="bg-black/60 rounded-full p-1.5">
                      <ZoomIn size={14} className="text-white" />
                    </div>
                  </div>
                </button>
              </div>
            )}
            {/* Don't render a text bubble for quiz-card messages — the amber card below is the UI */}
            {!m.quizId && (
              <div className={`max-w-[88%] px-4 py-3 rounded-2xl text-sm leading-relaxed
                ${m.role === 'user'
                  ? 'bg-indigo-600 text-white rounded-br-md'
                  : 'bg-[var(--surface)] border border-[var(--bd)] text-[var(--tx2)] rounded-bl-md'}`}>
                {m.role === 'assistant'
                  ? <div className="ai-content"><ReactMarkdown
                      remarkPlugins={[remarkMath]}
                      rehypePlugins={[[rehypeKatex, KATEX_OPTIONS]]}
                      components={{
                        code({ className, children }) {
                          const lang = /language-(\w+)/.exec(className ?? '')?.[1];
                          if (lang === 'smiles') return <SmilesBlock smiles={String(children).trim()} />;
                          return <code className={className}>{children}</code>;
                        },
                      }}
                    >{preprocessMath(m.content)}</ReactMarkdown></div>
                  : m.content}
              </div>
            )}
            {m.role === 'assistant' && m.videoId && (
              <div className="max-w-[88%] w-full mt-2">
                <VideoStatusCard
                  videoId={m.videoId}
                  token={token ?? undefined}
                  onDelete={() => setMessages(prev => prev.map((m2, j) => j === i ? { ...m2, videoId: undefined } : m2))}
                />
              </div>
            )}
            {m.role === 'assistant' && m.quizId && (
              <div className="max-w-[88%] w-full mt-2">
                <StudyQuizCard
                  quizId={m.quizId}
                  quizTopic={m.quizTopic}
                  quizQuestionCount={m.quizQuestionCount}
                  returnUrl={`/study/${ss.id}?tab=chat${convId ? `&conv=${convId}` : ''}`}
                  token={token ?? undefined}
                />
              </div>
            )}
            {/* Action buttons — shown under every AI message except quiz cards */}
            {m.role === 'assistant' && !m.quizId && !loading && (
              <div className="max-w-[88%] mt-1.5 flex flex-wrap gap-2">
                {!m.videoId && (
                  <button
                    onClick={() => handlePerMessageAction('Create a video', m.content, m.id, i)}
                    disabled={videoing}
                    className="text-xs px-3 py-1.5 rounded-lg flex items-center gap-1.5 font-medium transition-all
                               bg-purple-600/25 hover:bg-purple-600/40 text-[var(--purple)]
                               border border-purple-500/25 disabled:opacity-40">
                    {videoing ? <Loader size={11} className="animate-spin" /> : '🎬'}
                    {tChat.chat.animateIt.replace('🎬 ', '')}
                  </button>
                )}
                <button
                  onClick={() => handlePerMessageAction('Quiz me on this', m.content, m.id, i)}
                  disabled={quizzing}
                  className="text-xs px-3 py-1.5 rounded-lg flex items-center gap-1.5 font-medium transition-all
                             bg-indigo-500/10 hover:bg-indigo-500/20 text-[var(--indigo)]
                             border border-indigo-500/20 disabled:opacity-40">
                  {quizzing ? <Loader size={11} className="animate-spin" /> : '✏️'}
                  {tChat.chat.quizMe.replace('✏️ ', '')}
                </button>
              </div>
            )}
            {/* Suggestion chips on last message — AI-generated contextual follow-up questions */}
            {m.role === 'assistant' && !m.quizId && i === messages.length - 1 && !loading && (
              <div className="max-w-[88%] mt-1 flex flex-wrap gap-1.5">
                <>
                    {(m.chips ?? [])
                      .filter(c => !['Sketch it', 'Give me an example', 'Explain differently', 'Create a video', 'Quiz me on this'].includes(c))
                      .map(c => (
                        <button key={c} onClick={() => handleChip(c)}
                          className="text-xs px-3 py-1.5 rounded-full transition-all
                                     border border-[var(--bd)] hover:border-[var(--bd2)]
                                     text-[var(--tx5)] hover:text-[var(--tx2)] hover:bg-[var(--ov1)]">
                          {decodeHtml(c)}
                        </button>
                      ))
                    }
                    <button
                      onClick={() => fireMessage('Give me a concrete real-world example of this')}
                      className="text-xs px-3 py-1.5 rounded-full transition-all
                                 border border-amber-500/20 hover:border-amber-500/35
                                 text-[var(--amber)] hover:text-[var(--amber)]">
                      💡 Show me an example
                    </button>
                  </>
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

      {/* Pinned PDF context chip */}
      {pinnedCtx && (
        <div className="flex items-center gap-2 mb-2 px-3 py-2 rounded-xl
                        bg-indigo-500/8 border border-indigo-500/20 shrink-0">
          {pinnedCtx.imageDataUrl && (
            <img src={pinnedCtx.imageDataUrl} alt=""
              className="h-10 w-auto rounded-lg border border-indigo-500/25 object-contain bg-white shrink-0"
              style={{ maxWidth: '80px' }} />
          )}
          <div className="flex-1 min-w-0">
            <p className="text-[11px] text-indigo-300 font-medium">
              {pinnedCtx.type === 'region' ? '📌 Region from' : '📄 Page'}{' '}
              {pinnedCtx.type === 'region' ? `page ${pinnedCtx.pageNum}` : pinnedCtx.pageNum}
              {pinnedCtx.mode === 'text' ? ' (text)' : ' (image)'}
            </p>
            {pinnedCtx.text && (
              <p className="text-[10px] text-indigo-300/50 truncate mt-0.5">{pinnedCtx.text.slice(0, 80)}…</p>
            )}
          </div>
          <button onClick={onClearCtx} className="text-indigo-400/40 hover:text-indigo-400 transition-colors shrink-0">
            <XIcon size={13} />
          </button>
        </div>
      )}

      {/* Input */}
      <div className="flex gap-2 pt-3 border-t border-[var(--bd)] shrink-0">
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
          disabled={notReady || loading}
          placeholder={notReady ? 'Waiting for PDF processing…' : `Ask about ${ss.title}…`}
          className="flex-1 px-4 py-2.5 rounded-xl bg-[var(--ov2)] border border-[var(--bd)]
                     text-[var(--tx1)] text-sm placeholder-[var(--tx7)]
                     focus:outline-none focus:border-indigo-500/50 disabled:opacity-50 transition-colors" />
        <button onClick={handleDebug} title="Debug: inspect prompt sent to AI"
          className="w-10 h-10 flex items-center justify-center rounded-xl border border-[var(--bd)]
                     text-[var(--tx6)] hover:text-amber-400 hover:border-amber-400/30 transition-colors">
          <Bug size={15} />
        </button>
        <button onClick={send} disabled={!input.trim() || loading || notReady}
          className="w-10 h-10 flex items-center justify-center rounded-xl
                     bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white transition-colors">
          <Send size={15} />
        </button>
      </div>

      {/* Image lightbox */}
      {lightboxSrc && (
        <ImageLightbox src={lightboxSrc} onClose={() => setLightboxSrc(null)} />
      )}

      {debugData && <DebugPromptModal data={debugData} onClose={() => setDebugData(null)} />}
    </div>
  );
}

// ─── ChatTab ─── split container ─────────────────────────────────────────────

function ChatTab({
  ss, convs, openWithConceptId, pdfFile, onLoadPdf, onNewConversation,
}: {
  ss: StudySetDetail;
  convs: StudySetConversation[];
  openWithConceptId?: string | null;
  pdfFile: File | null;
  onLoadPdf: () => void;
  onNewConversation?: (convId: string) => void;
}) {
  // null = General chat, string = concept ID
  const [activeConceptId, setActiveConceptId] = useState<string | null>(openWithConceptId ?? null);
  const [pdfOpen,     setPdfOpen]     = useState(false);
  const [pendingFire, setPendingFire] = useState<{ text: string; imageDataUrl?: string } | null>(null);
  const [pinnedCtx,   setPinnedCtx]   = useState<PinnedCtx | null>(null);

  // When parent navigates to a concept (e.g. from Concepts tab)
  useEffect(() => {
    if (openWithConceptId !== undefined) setActiveConceptId(openWithConceptId ?? null);
  }, [openWithConceptId]);

  // Auto-open when a PDF is loaded in
  useEffect(() => { if (pdfFile) setPdfOpen(true); }, [pdfFile]);

  function handleFire(prompt: string, imageDataUrl?: string) {
    setPendingFire({ text: prompt, imageDataUrl });
  }

  const hasMaterial = ss.materials.some(m => m.status === 'ready' && m.file_url);
  const hasConcepts = ss.concepts.length > 0;

  // Find the existing conversation for the current selection
  const activeConv = activeConceptId
    ? (convs.find(c => c.study_concept_id === activeConceptId) ?? null)
    : (convs.find(c => !c.study_concept_id) ?? null);

  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">

      {/* ── Concept sidebar ─────────────────────────────────────── */}
      {hasConcepts && !pdfOpen && (
        <div className="hidden sm:flex w-44 shrink-0 border-r border-[var(--bd)] flex-col min-h-0">
          <div className="px-2 pt-3 pb-1.5 shrink-0">
            <p className="text-[10px] font-semibold text-[var(--tx6)] uppercase tracking-wider px-2">Chats</p>
          </div>
          <div className="flex-1 overflow-y-auto chat-scroll pb-2">
            {/* General */}
            <button
              onClick={() => setActiveConceptId(null)}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-colors
                          ${!activeConceptId
                ? 'bg-indigo-500/10 text-indigo-300'
                : 'text-[var(--tx4)] hover:text-[var(--tx2)] hover:bg-[var(--ov1)]'}`}>
              <BookOpen size={12} className="shrink-0" />
              <span className="text-xs truncate">General</span>
              {convs.some(c => !c.study_concept_id) && (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />
              )}
            </button>

            <div className="h-px bg-[var(--bd)] mx-2 my-1" />

            {/* Per-concept */}
            {ss.concepts.map(c => {
              const hasConv = convs.some(cv => cv.study_concept_id === c.id);
              const isActive = activeConceptId === c.id;
              return (
                <button key={c.id}
                  onClick={() => setActiveConceptId(c.id)}
                  className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-colors
                              ${isActive
                    ? 'bg-indigo-500/10 text-indigo-300'
                    : 'text-[var(--tx4)] hover:text-[var(--tx2)] hover:bg-[var(--ov1)]'}`}>
                  <div className={`w-1.5 h-1.5 rounded-full shrink-0 mt-px
                                   ${hasConv ? 'bg-indigo-400' : 'bg-[var(--tx7)]'}`} />
                  <span className="text-xs truncate flex-1">{c.name}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* ── PDF pane ─────────────────────────────────────────────── */}
      {pdfFile && pdfOpen && (
        <div className="w-[44%] min-w-[280px] max-w-[520px] border-r border-[var(--bd)] flex flex-col min-h-0 shrink-0">
          <StudyPDFPane
            file={pdfFile}
            onClose={() => setPdfOpen(false)}
            onFire={handleFire}
            onPin={ctx => setPinnedCtx(ctx)}
          />
        </div>
      )}

      {/* ── Chat panel ───────────────────────────────────────────── */}
      <div className="flex-1 min-w-0 flex flex-col min-h-0 px-4 sm:px-5 py-4">
        {hasMaterial && (
          <div className="flex items-center gap-2 pb-2 mb-2 border-b border-[var(--bd)] shrink-0">
            {pdfFile && pdfOpen ? null : (
              <button
                onClick={pdfFile ? () => setPdfOpen(true) : onLoadPdf}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                           border border-[var(--bd)] text-[var(--tx5)] hover:text-indigo-400
                           hover:border-indigo-500/30 hover:bg-indigo-500/5 transition-all">
                <FileText size={12} /> {pdfFile ? 'Show PDF' : 'Open PDF'}
              </button>
            )}
          </div>
        )}
        <ActiveChat
          key={activeConceptId ?? 'general'}
          ss={ss}
          studyConceptId={activeConceptId}
          loadConversation={activeConv}
          pendingFire={pendingFire}
          onFired={() => setPendingFire(null)}
          pinnedCtx={pinnedCtx}
          onClearCtx={() => setPinnedCtx(null)}
          onNewConversation={onNewConversation}
        />
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function StudySetPage() {
  const params       = useParams();
  const router       = useRouter();
  const searchParams = useSearchParams();
  const { token, user, sessionId, setSessionId } = useSessionStore();
  const { t } = useTranslation();
  const id           = params.id as string;

  const [ss,       setSs]       = useState<StudySetDetail | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [tab,      setTab]      = useState<Tab>(
    (searchParams.get('tab') as Tab | null) ?? 'overview'
  );

  // Which concept to open in ChatTab (null = General)
  const [openWithConceptId, setOpenWithConceptId] = useState<string | null | undefined>(undefined);

  // Conversations list — loaded once, refreshed on new conversation
  const [convs, setConvs] = useState<StudySetConversation[]>([]);

  // PDF state
  const [pdfMaterial, setPdfMaterial] = useState<StudyMaterial | null>(null);
  const [pdfFile,     setPdfFile]     = useState<File | null>(null);
  const [pdfLoading,  setPdfLoading]  = useState(false);
  const [pdfError,    setPdfError]    = useState<string | null>(null);

  const pollRef          = useRef<ReturnType<typeof setTimeout> | null>(null);
  const urlRestoredRef   = useRef(false);

  // Init anonymous session if arriving directly on this page
  useEffect(() => {
    if (!sessionId && !user) {
      createSession().then(s => setSessionId(s.session_id)).catch(() => {});
    }
  }, []);

  const load = useCallback(async () => {
    try {
      const data = await getStudySet(id, token ?? undefined, user?.id);
      setSs(data);
      if (data.status === 'processing') setTab('overview');
      return data.status;
    } catch { return 'error'; }
    finally { setLoading(false); }
  }, [id, token, user?.id]);

  useEffect(() => {
    load().then(s => { if (s === 'processing') startPoll(); });
    return () => { if (pollRef.current) clearTimeout(pollRef.current); };
  }, []);

  // Load conversations when study set is ready
  useEffect(() => {
    if (!ss || ss.status !== 'ready') return;
    getStudySetConversations(ss.id, token ?? undefined)
      .then(r => setConvs(r))
      .catch(() => {});
  }, [ss?.id, ss?.status]);

  // Restore active conversation from URL on refresh — navigate to its concept
  useEffect(() => {
    if (urlRestoredRef.current || !convs.length) return;
    const convParam = new URLSearchParams(window.location.search).get('conv');
    if (!convParam) return;
    urlRestoredRef.current = true;
    const found = convs.find(c => c.id === convParam);
    if (found) {
      setOpenWithConceptId(found.study_concept_id ?? null);
      setTab('chat');
    }
  }, [convs]);

  function startPoll() {
    pollRef.current = setTimeout(async () => {
      const s = await load(); if (s === 'processing') startPoll();
    }, 4000);
  }

  function handleUploaded() { load().then(() => startPoll()); }

  // Navigate to Chat tab focused on a specific concept
  function handleConceptChat(conceptId: string) {
    setOpenWithConceptId(conceptId);
    setTab('chat');
  }

  // Open PDF — loads bytes, switches to chat tab where the split pane lives
  async function handleOpenPdf(mat: StudyMaterial) {
    setPdfLoading(true);
    setPdfMaterial(mat);
    setPdfError(null);
    try {
      const file = await fetchMaterialPdf(id, mat.id, mat.filename, token ?? undefined, mat.file_url);
      setPdfFile(file);
      setTab('chat');  // Switch to chat tab — ChatTab will auto-open the PDF pane
    } catch (e: any) {
      setPdfError(e?.message || 'Could not load PDF — please try re-uploading.');
      setPdfMaterial(null);
    } finally { setPdfLoading(false); }
  }

  // When user asks from PDF selection
  const TABS: { key: Tab; label: string; icon: React.ReactNode; disabled?: boolean }[] = [
    { key: 'overview',   label: t.studySets.tabOverview,   icon: <BookOpen size={13} /> },
    { key: 'concepts',   label: t.studySets.tabConcepts,   icon: <FileText size={13} />,   disabled: ss?.status !== 'ready' },
    { key: 'flashcards', label: t.studySets.tabFlashcards, icon: <LayoutGrid size={13} />, disabled: ss?.status !== 'ready' },
    { key: 'chat',       label: t.studySets.tabChat,       icon: <MessageSquare size={13} />, disabled: ss?.status !== 'ready' },
    { key: 'diagrams',   label: t.studySets.tabDiagrams,   icon: <ImageIcon size={13} />,  disabled: ss?.status !== 'ready' },
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
      <main className="flex-1 flex items-center justify-center text-[var(--tx5)]">{t.studySets.notFound}</main>
    </div>
  );

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
      <Sidebar onNewChat={() => router.push('/')} />

      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <MobileTopBar />
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

        {/* PDF load error banner */}
        {pdfError && (
          <div className="mx-4 sm:mx-6 mt-3 flex items-start gap-2.5 px-4 py-3 rounded-xl
                          bg-red-500/8 border border-red-500/20 text-red-400 text-xs leading-relaxed">
            <AlertCircle size={13} className="shrink-0 mt-0.5" />
            <span>{pdfError}</span>
            <button onClick={() => setPdfError(null)} className="ml-auto shrink-0 text-red-400/50 hover:text-red-400">
              ×
            </button>
          </div>
        )}

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

        {/* Non-chat tabs — scrollable */}
        {tab !== 'chat' && (
          <div className="flex-1 chat-scroll px-4 sm:px-6 py-6">
            {tab === 'overview' && (
              <OverviewTab ss={ss} onRefresh={handleUploaded} onOpenPdf={handleOpenPdf} />
            )}
            {tab === 'concepts' && (
              <ConceptsTab ss={ss} onChat={handleConceptChat} onConceptsGenerated={load} />
            )}
            {tab === 'flashcards' && <FlashcardsTab ss={ss} />}
            {tab === 'diagrams' && (
              <DiagramsGallery
                studySetId={ss.id}
                userId={user?.id}
                sessionId={sessionId ?? undefined}
                token={token ?? undefined}
              />
            )}
          </div>
        )}

        {/*
          Chat tab — always mounted so component state (messages, convId, PDF pane)
          survives tab switches. CSS hidden when another tab is active.
        */}
        <div className={tab === 'chat' ? 'flex flex-1 min-h-0 overflow-hidden' : 'hidden'}>
          <ChatTab
            ss={ss}
            convs={convs}
            openWithConceptId={openWithConceptId}
            pdfFile={pdfFile}
            onLoadPdf={() => {
              const mat = ss.materials.find(m => m.status === 'ready' && m.file_url);
              if (mat) handleOpenPdf(mat);
            }}
            onNewConversation={() => {
              getStudySetConversations(ss.id, token ?? undefined)
                .then(r => setConvs(r))
                .catch(() => {});
            }}
          />
        </div>
      </main>

      {/* PDFViewerModal removed — PDF now opens inline beside chat */}
    </div>
  );
}
