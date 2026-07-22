'use client';
import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import ReactMarkdown from 'react-markdown';
import {
  ArrowLeft, Send, Loader2, Video, BookOpen,
  Scissors, ChevronDown, Check, Sparkles,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';
import {
  StudioMessage, sendStudioChatMessage,
  addContentBlock, generateBlockVideo,
} from '@/lib/api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const StudyPDFPane = dynamic(
  () => import('@/components/study/StudyPDFPane').then(m => m.StudyPDFPane),
  { ssr: false, loading: () => <div className="flex-1 flex items-center justify-center text-[var(--tx7)] text-sm">Loading PDF…</div> },
);

// ── Section parsing ───────────────────────────────────────────────────────────

function parseStudioSections(content: string): { explanation: string | null; videoScript: string | null } {
  const explanationMatch = content.match(/###\s*EXPLANATION\s*\n([\s\S]*?)(?=###\s*VIDEO SCRIPT|$)/i);
  const videoScriptMatch = content.match(/###\s*VIDEO SCRIPT\s*\n([\s\S]*?)$/i);
  return {
    explanation: explanationMatch ? explanationMatch[1].trim() : null,
    videoScript: videoScriptMatch ? videoScriptMatch[1].trim() : null,
  };
}

// ── Concept picker dropdown ───────────────────────────────────────────────────

interface ConceptOption { id: string; title: string; }

function ConceptPicker({
  concepts,
  label,
  icon,
  busy,
  onSelect,
}: {
  concepts: ConceptOption[];
  label: string;
  icon: React.ReactNode;
  busy: boolean;
  onSelect: (concept: ConceptOption) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        disabled={busy}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border border-[var(--bd)]
                   text-[var(--tx5)] hover:border-purple-500/40 hover:text-purple-400 transition-all
                   disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {busy ? <Loader2 size={12} className="animate-spin" /> : icon}
        {label}
        <ChevronDown size={10} />
      </button>
      {open && (
        <div className="absolute bottom-full mb-1 left-0 z-50 w-56 bg-[var(--bg2)] border border-[var(--bd)]
                        rounded-xl shadow-xl overflow-hidden">
          {concepts.length === 0 ? (
            <p className="px-3 py-2 text-xs text-[var(--tx7)]">No concepts in this chapter yet</p>
          ) : (
            concepts.map(c => (
              <button
                key={c.id}
                onClick={() => { onSelect(c); setOpen(false); }}
                className="w-full text-left px-3 py-2 text-xs text-[var(--tx3)] hover:bg-[var(--ov1)]
                           border-b border-[var(--bd)] last:border-0 truncate"
              >
                {c.title}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ── Studio message bubble ─────────────────────────────────────────────────────

function StudioBubble({
  msg,
  concepts,
  token,
  onSaved,
}: {
  msg: StudioMessage;
  concepts: ConceptOption[];
  token: string;
  onSaved: (conceptId: string, type: 'text' | 'video', title: string) => void;
}) {
  const { explanation, videoScript } = msg.role === 'assistant'
    ? parseStudioSections(msg.content)
    : { explanation: null, videoScript: null };

  const hasSections = explanation !== null || videoScript !== null;
  const [savingText, setSavingText]   = useState(false);
  const [savingVideo, setSavingVideo] = useState(false);
  const [saved, setSaved]             = useState<string | null>(null);

  async function handleSaveText(concept: ConceptOption) {
    if (!explanation) return;
    setSavingText(true);
    try {
      await addContentBlock(concept.id, {
        type:  'text',
        title: concept.title + ' — Explanation',
        body:  explanation,
      }, token);
      setSaved(`Text saved to "${concept.title}"`);
      onSaved(concept.id, 'text', concept.title);
    } catch (e: any) {
      alert('Failed to save: ' + e.message);
    } finally {
      setSavingText(false);
    }
  }

  async function handleGenerateVideo(concept: ConceptOption) {
    if (!videoScript) return;
    setSavingVideo(true);
    try {
      await generateBlockVideo(concept.id, {
        title:      concept.title + ' — Video',
        transcript: videoScript,
      }, token);
      setSaved(`Video queued for "${concept.title}"`);
      onSaved(concept.id, 'video', concept.title);
    } catch (e: any) {
      alert('Failed to queue video: ' + e.message);
    } finally {
      setSavingVideo(false);
    }
  }

  if (msg.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] px-4 py-2.5 rounded-2xl rounded-tr-sm bg-purple-600/20
                        border border-purple-500/20 text-[var(--tx2)] text-sm whitespace-pre-wrap">
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="prose prose-sm prose-invert max-w-none px-1 text-[var(--tx3)]
                      [&_h3]:text-[var(--tx2)] [&_h3]:font-semibold [&_h3]:mt-4 [&_h3]:mb-2
                      [&_p]:text-[var(--tx4)] [&_p]:leading-relaxed">
        <ReactMarkdown>{msg.content}</ReactMarkdown>
      </div>

      {hasSections && (
        <div className="flex flex-wrap gap-2 mt-1 pt-2 border-t border-[var(--bd)]">
          {saved && (
            <span className="flex items-center gap-1 text-xs text-emerald-400">
              <Check size={12} /> {saved}
            </span>
          )}
          {explanation && (
            <ConceptPicker
              concepts={concepts}
              label="Save explanation"
              icon={<BookOpen size={12} />}
              busy={savingText}
              onSelect={handleSaveText}
            />
          )}
          {videoScript && (
            <ConceptPicker
              concepts={concepts}
              label="Generate video"
              icon={<Video size={12} />}
              busy={savingVideo}
              onSelect={handleGenerateVideo}
            />
          )}
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function TeacherStudioPage() {
  const router     = useRouter();
  const params     = useParams();
  const courseId   = params.id as string;
  const chapterId  = params.chapterId as string;
  const { user, token } = useSessionStore();

  const [chapterFile,    setChapterFile]    = useState<File | null>(null);
  const [concepts,       setConcepts]       = useState<ConceptOption[]>([]);
  const [chapterName,    setChapterName]    = useState('Chapter');
  const [loading,        setLoading]        = useState(true);
  const [showPdf,        setShowPdf]        = useState(true);

  const [messages,       setMessages]       = useState<StudioMessage[]>([]);
  const [input,          setInput]          = useState('');
  const [sending,        setSending]        = useState(false);
  const [pinnedImage,    setPinnedImage]    = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!user) { router.replace('/auth/teacher'); return; }
    loadChapter();
  }, [user, chapterId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function loadChapter() {
    setLoading(true);
    try {
      // Load PDF bytes
      const pdfRes = await fetch(`${API_BASE}/api/courses/chapters/${chapterId}/pdf`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (pdfRes.ok) {
        const blob = await pdfRes.blob();
        // Try to get filename from Content-Disposition header
        const cd = pdfRes.headers.get('Content-Disposition') || '';
        const nameMatch = cd.match(/filename="?([^"]+)"?/);
        const filename  = nameMatch ? nameMatch[1] : 'chapter.pdf';
        setChapterFile(new File([blob], filename, { type: 'application/pdf' }));
        setChapterName(filename.replace(/\.pdf$/i, ''));
      }

      // Load concepts in this chapter's unit
      const courseRes = await fetch(`${API_BASE}/api/courses/${courseId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (courseRes.ok) {
        const course = await courseRes.json();
        const unit = (course.units || []).find((u: any) => u.chapter_ref === chapterId);
        if (unit) {
          setConcepts(unit.concepts.map((c: any) => ({ id: c.id, title: c.title })));
          setChapterName(unit.title || chapterName);
        }
      }
    } catch (e) {
      console.error('Studio load error:', e);
    } finally {
      setLoading(false);
    }
  }

  const handleSend = useCallback(async (overrideInput?: string) => {
    const text = (overrideInput ?? input).trim();
    if (!text && !pinnedImage) return;
    if (sending) return;

    const userMsg: StudioMessage = { role: 'user', content: text };
    const history = [...messages];
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setPinnedImage(null);
    setSending(true);

    try {
      const reply = await sendStudioChatMessage(chapterId, {
        message:        text,
        history:        history.slice(-20).map(m => ({ role: m.role, content: m.content })),
        image_data_url: pinnedImage ?? null,
      }, token!);
      setMessages(prev => [...prev, reply]);
    } catch (e: any) {
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${e.message}` }]);
    } finally {
      setSending(false);
    }
  }, [input, messages, sending, chapterId, token, pinnedImage]);

  function handlePDFFire(prompt: string, imageDataUrl?: string) {
    if (imageDataUrl) setPinnedImage(imageDataUrl);
    handleSend(prompt);
  }

  function handlePDFPin(ctx: any) {
    if (ctx.imageDataUrl) {
      setPinnedImage(ctx.imageDataUrl);
    }
  }

  function handleSaved(conceptId: string, type: 'text' | 'video', title: string) {
    // Refresh concepts to update the dropdown (in case new ones were added elsewhere)
  }

  if (!user) return null;

  return (
    <div className="h-screen flex flex-col bg-[var(--bg1)]">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-[var(--bd)] shrink-0">
        <button onClick={() => router.back()} className="text-[var(--tx6)] hover:text-[var(--tx3)] transition-colors">
          <ArrowLeft size={18} />
        </button>
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-purple-400" />
          <h1 className="text-sm font-semibold text-[var(--tx2)]">Studio — {chapterName}</h1>
        </div>
        <div className="flex-1" />
        <button
          onClick={() => setShowPdf(v => !v)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border transition-all
            ${showPdf ? 'border-purple-500/40 text-purple-400' : 'border-[var(--bd)] text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400'}`}
        >
          <BookOpen size={12} /> PDF
        </button>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center text-[var(--tx7)] text-sm gap-2">
          <Loader2 size={16} className="animate-spin" /> Loading studio…
        </div>
      ) : (
        <div className="flex-1 flex overflow-hidden">
          {/* PDF pane */}
          {showPdf && chapterFile && (
            <div className="w-[45%] border-r border-[var(--bd)] flex flex-col overflow-hidden">
              <StudyPDFPane
                file={chapterFile}
                onClose={() => setShowPdf(false)}
                onFire={handlePDFFire}
                onPin={handlePDFPin}
              />
            </div>
          )}

          {/* Chat pane */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
                  <Sparkles size={28} className="text-purple-400/60" />
                  <p className="text-[var(--tx5)] text-sm max-w-xs">
                    Ask me to draft an explanation or video script for any topic in this chapter.
                    {chapterFile && ' Clip a region from the PDF to include it in your question.'}
                  </p>
                  <div className="flex flex-wrap gap-2 justify-center">
                    {[
                      'Draft an explanation for the first concept',
                      'Write a video script for the key formula',
                      'Summarise the main ideas in 3 bullet points',
                    ].map(s => (
                      <button
                        key={s}
                        onClick={() => { setInput(s); }}
                        className="px-3 py-1.5 rounded-full text-xs border border-[var(--bd)]
                                   text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400 transition-all"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((msg, i) => (
                <StudioBubble
                  key={i}
                  msg={msg}
                  concepts={concepts}
                  token={token!}
                  onSaved={handleSaved}
                />
              ))}

              {sending && (
                <div className="flex gap-1.5 px-1 py-2">
                  {[0, 1, 2].map(i => (
                    <span key={i} className="w-1.5 h-1.5 rounded-full bg-purple-400/60 animate-bounce"
                          style={{ animationDelay: `${i * 0.15}s` }} />
                  ))}
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {/* Pinned image indicator */}
            {pinnedImage && (
              <div className="px-4 py-2 border-t border-[var(--bd)] flex items-center gap-2">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={pinnedImage} alt="clip" className="h-10 w-16 object-cover rounded border border-[var(--bd)]" />
                <span className="text-xs text-[var(--tx6)] flex-1">PDF clip attached</span>
                <button onClick={() => setPinnedImage(null)} className="text-[var(--tx7)] hover:text-[var(--tx3)] text-xs">✕</button>
              </div>
            )}

            {/* Input */}
            <div className="px-4 py-3 border-t border-[var(--bd)] flex gap-2">
              <textarea
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                placeholder="Ask for an explanation, video script, or revision…"
                rows={2}
                className="flex-1 resize-none bg-[var(--bg2)] border border-[var(--bd)] rounded-xl px-3 py-2
                           text-sm text-[var(--tx2)] placeholder:text-[var(--tx7)] focus:outline-none
                           focus:border-purple-500/50 transition-colors"
              />
              <button
                onClick={() => handleSend()}
                disabled={sending || (!input.trim() && !pinnedImage)}
                className="self-end px-3 py-2 rounded-xl bg-purple-600 text-white text-sm
                           hover:bg-purple-500 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {sending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
