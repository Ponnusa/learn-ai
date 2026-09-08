'use client';
import { useState, useEffect, useRef } from 'react';
import { X, Compass, Loader2, Send } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { useTranslation } from '@/hooks/useTranslation';
import { sendMessage } from '@/lib/api';
import { preprocessMath } from '@/lib/preprocessMath';
import { KATEX_OPTIONS } from '@/lib/mathConfig';

export interface ExploratoryResult {
  steps: number;
  resolved: boolean;
}

interface ExploratoryPanelProps {
  topic: string;
  userId?: string;
  sessionId?: string;
  token?: string;
  language: string;
  onClose: (result: ExploratoryResult | null) => void;
}

/**
 * Guided-discovery overlay — launched via the "Walk me through it" action on
 * any assistant message (MessageBubble), never a whole-conversation toggle.
 * Runs its own separate conversation (mode: 'exploratory') so the Socratic
 * back-and-forth never lands in the main chat log; only a one-line summary
 * does, via onClose(), once the student exits or resolves the ladder.
 */
export function ExploratoryPanel({ topic, userId, sessionId, token, language, onClose }: ExploratoryPanelProps) {
  const { t } = useTranslation();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [question, setQuestion] = useState<string | null>(null);
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(true);
  const [depth, setDepth] = useState(0);
  const [maxDepth, setMaxDepth] = useState(0);
  const [resolved, setResolved] = useState(false);
  const [visible, setVisible] = useState(false);
  const [errored, setErrored] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const started = useRef(false);

  useEffect(() => {
    // Deliberate: paint at opacity-0/scale-95 first, then flip on the next
    // tick so the CSS transition actually animates in, rather than starting
    // already-visible with nothing to transition from.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setVisible(true);
    if (started.current) return;
    started.current = true;
    sendMessage({
      message: `Let's explore this together: ${topic}`,
      user_id: userId,
      session_id: sessionId,
      language,
      mode: 'exploratory',
    }, token).then(res => {
      setConversationId(res.conversation_id);
      setQuestion(res.reply);
      setDepth(res.ladder_depth ?? 0);
      setMaxDepth(res.ladder_depth ?? 0);
    }).catch(() => setErrored(true))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!loading) inputRef.current?.focus();
  }, [loading, question]);

  async function submitAnswer() {
    if (!answer.trim() || !conversationId || loading) return;
    setLoading(true);
    const submitted = answer;
    setAnswer('');
    try {
      const res = await sendMessage({
        message: submitted,
        conversation_id: conversationId,
        user_id: userId,
        session_id: sessionId,
        language,
        mode: 'exploratory',
      }, token);
      const newDepth = res.ladder_depth ?? 0;
      setQuestion(res.reply);
      // Resolved = we went deeper into the ladder at some point and just came
      // back to depth 0 — not the same as "started at depth 0" (first question).
      if (newDepth === 0 && maxDepth > 0) setResolved(true);
      setDepth(newDepth);
      setMaxDepth(m => Math.max(m, newDepth));
    } catch {
      setAnswer(submitted); // let the student retry rather than losing their answer
    } finally {
      setLoading(false);
    }
  }

  function handleClose() {
    setVisible(false);
    setTimeout(() => onClose(conversationId ? { steps: maxDepth, resolved } : null), 200);
  }

  const dotCount = Math.max(maxDepth, depth) + 1;

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm
                  transition-opacity duration-200 ${visible ? 'opacity-100' : 'opacity-0'}`}
      onClick={e => { if (e.target === e.currentTarget) handleClose(); }}
    >
      <div
        className={`w-full max-w-lg rounded-2xl bg-[var(--surface)] border border-[var(--bd)]
                    shadow-2xl p-6 transition-all duration-200
                    ${visible ? 'translate-y-0 scale-100' : 'translate-y-2 scale-95'}`}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2 text-[var(--indigo)]">
            <Compass size={18} />
            <span className="text-sm font-semibold">{topic.length > 60 ? `${topic.slice(0, 60)}…` : topic}</span>
          </div>
          <button
            onClick={handleClose}
            aria-label={t.chat.exploratoryExit}
            className="text-[var(--txa)] hover:text-[var(--tx4)] p-1 rounded-lg hover:bg-[var(--ov1)] transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Ladder-depth breadcrumb */}
        <div className="flex items-center gap-1.5 mb-5">
          {Array.from({ length: dotCount }, (_, i) => (
            <div
              key={i}
              className={`h-2 rounded-full transition-all duration-300 ${
                i === depth && !resolved ? 'w-6 bg-[var(--indigo)]'
                : i < depth || resolved ? 'w-2 bg-[var(--indigo)]/40'
                : 'w-2 bg-[var(--bd2)]'
              }`}
            />
          ))}
          {resolved && (
            <span className="ml-2 text-xs text-[var(--green)]" style={{ animation: 'fadeIn 0.4s ease' }}>
              ✓ {t.chat.exploratoryResolved}
            </span>
          )}
        </div>

        {/* Current question/step — key forces a fresh fade-in each time it changes */}
        <div key={question ?? 'loading'} className="min-h-[70px] mb-5" style={{ animation: 'fadeIn 0.3s ease-out' }}>
          {loading && !question ? (
            <div className="flex items-center gap-2 text-[var(--tx8)] text-sm">
              <Loader2 size={14} className="animate-spin" />
            </div>
          ) : errored ? (
            <p className="text-sm text-[var(--tx8)]">Something went wrong starting this — try again in a moment.</p>
          ) : question ? (
            <div className="ai-content text-[15px]">
              <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[[rehypeKatex, KATEX_OPTIONS]]}>
                {preprocessMath(question)}
              </ReactMarkdown>
            </div>
          ) : null}
        </div>

        {resolved ? (
          <button
            onClick={handleClose}
            className="w-full text-sm px-4 py-2.5 rounded-lg font-medium bg-[var(--indigo)] text-white hover:opacity-90 transition-all"
          >
            {t.chat.exploratoryBackToChat}
          </button>
        ) : (
          <>
            <div className="flex items-end gap-2">
              <textarea
                ref={inputRef}
                value={answer}
                onChange={e => setAnswer(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitAnswer(); } }}
                placeholder={t.chat.exploratoryPlaceholder}
                rows={1}
                disabled={loading || errored}
                className="flex-1 resize-none rounded-lg border border-[var(--bd)] bg-[var(--bg)]
                           px-3 py-2 text-sm focus:outline-none focus:border-[var(--indigo)]
                           disabled:opacity-50 text-[var(--tx2)]"
              />
              <button
                onClick={submitAnswer}
                disabled={loading || errored || !answer.trim()}
                className="p-2.5 rounded-lg bg-[var(--indigo)] text-white disabled:opacity-40 transition-all shrink-0"
              >
                {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              </button>
            </div>
            <button
              onClick={handleClose}
              className="mt-3 text-xs text-[var(--tx8)] hover:text-[var(--tx4)] transition-colors"
            >
              {t.chat.exploratoryExit}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
