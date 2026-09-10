import { useEffect, useRef, useState } from 'react';
import type { Components } from 'react-markdown';
import { Copy, Check, Loader, Square, Volume2 } from 'lucide-react';
import { MathText } from '../components/MathText';
import { SmilesBlock } from '../components/SmilesBlock';
import { getChatMessageAudio } from '../lib/api';
import type { GenieStrings } from '../lib/i18n';

export interface GenieMessageData {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  metadata?: {
    chips?: string[];
    /** Model's live self-report of guided-discovery depth — see
     *  frontend/components/chat/MessageBubble.tsx's Message interface for
     *  the full explanation. Hides the action toolbar while mid-chain. */
    ladder_depth?: number | null;
    /** A clipped screen region attached to this (user) message. */
    imageUrl?: string;
  };
}

interface GenieMessageProps {
  message: GenieMessageData;
  language?: string;
  t: GenieStrings;
  onChipClick?: (chip: string) => void;
  onQuizMe?: (content: string) => void;
  onWalkMeThrough?: () => void;
  onSimplify?: () => void;
  onGoDeeper?: () => void;
}

// At most one TTS clip plays at a time across all bubbles — same pattern as
// MessageBubble.tsx's module-level globalStopTts.
let globalStopTts: (() => void) | null = null;

const SMILES_COMPONENTS: Components = {
  code({ className, children }) {
    const lang = /language-(\w+)/.exec(className ?? '')?.[1];
    if (lang === 'smiles') return <SmilesBlock smiles={String(children).trim()} />;
    return <code className={className}>{children}</code>;
  },
};

// Full reply renderer — markdown, math/chemistry formulas, and organic
// structures (```smiles blocks -> SmilesBlock), plus the same action
// toolbar/chips/tertiary-actions as the web app's MessageBubble.tsx: quiz
// me, walk me through it, suggestion chips + "show me an example",
// simplify/go deeper, read-aloud, copy. No video/animate (genie doesn't
// offer video generation) and no quiz-card-in-thread (quiz has its own
// standalone GenieQuiz component instead of living inside a message).
export function GenieMessage({ message, language, t, onChipClick, onQuizMe, onWalkMeThrough, onSimplify, onGoDeeper }: GenieMessageProps) {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);
  const [ttsLoading, setTtsLoading] = useState(false);
  const [ttsPlaying, setTtsPlaying] = useState(false);
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null);
  // Genie doesn't do video generation itself — showing the button anyway
  // (rather than omitting it, which is what shipped before) matches the
  // app's actual toolbar and gives students a clear, honest next step
  // instead of a missing feature they might assume is just broken.
  const [showAnimateNotice, setShowAnimateNotice] = useState(false);

  const chips = message.metadata?.chips ?? [];
  const isMidScaffold = (message.metadata?.ladder_depth ?? 0) > 0;

  function stopTts() {
    if (ttsAudioRef.current) {
      ttsAudioRef.current.pause();
      ttsAudioRef.current.src = '';
      ttsAudioRef.current = null;
    }
    if (globalStopTts === stopTts) globalStopTts = null;
    setTtsPlaying(false);
  }

  useEffect(() => () => stopTts(), []);

  async function handleSpeak() {
    if (ttsPlaying || ttsLoading) {
      stopTts();
      setTtsLoading(false);
      return;
    }
    globalStopTts?.();
    globalStopTts = stopTts;
    setTtsLoading(true);
    try {
      const blob = await getChatMessageAudio(message.id, language ?? 'en');
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      ttsAudioRef.current = audio;
      audio.onended = () => {
        setTtsPlaying(false);
        URL.revokeObjectURL(url);
        ttsAudioRef.current = null;
        if (globalStopTts === stopTts) globalStopTts = null;
      };
      audio.onerror = () => {
        setTtsPlaying(false);
        ttsAudioRef.current = null;
        if (globalStopTts === stopTts) globalStopTts = null;
      };
      await audio.play();
      setTtsPlaying(true);
    } catch {
      setTtsPlaying(false);
      if (globalStopTts === stopTts) globalStopTts = null;
    } finally {
      setTtsLoading(false);
    }
  }

  function copy() {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (isUser) {
    const imageUrl = message.metadata?.imageUrl;
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl overflow-hidden bg-[var(--indigo)] text-white text-sm">
          {imageUrl && (
            <div className="px-3 pt-3 pb-1">
              <img
                src={imageUrl}
                alt={t.clipAttached}
                className="rounded-xl max-h-48 w-auto object-contain border border-white/20"
              />
            </div>
          )}
          <div className="px-3.5 py-2.5">{message.content}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[92%] rounded-2xl px-3.5 py-2.5 bg-[var(--surface)] border border-[var(--bd)] flex flex-col gap-2.5">
        <div className="ai-content">
          <MathText components={SMILES_COMPONENTS}>{message.content}</MathText>
        </div>

        {!isMidScaffold && (
          <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-[var(--bd2)]">
            <button
              onClick={() => setShowAnimateNotice((v) => !v)}
              className="text-[11px] px-2.5 py-1 rounded-lg font-medium bg-purple-600/25 hover:bg-purple-600/40 text-[var(--purple)] border border-purple-500/25"
            >
              {t.animateIt}
            </button>
            <button
              onClick={() => onQuizMe?.(message.content)}
              className="text-[11px] px-2.5 py-1 rounded-lg font-medium bg-indigo-500/10 hover:bg-indigo-500/20 text-[var(--indigo)] border border-indigo-500/20"
            >
              {t.quizMe}
            </button>
            <button
              onClick={() => onWalkMeThrough?.()}
              className="text-[11px] px-2.5 py-1 rounded-lg font-medium bg-indigo-500/10 hover:bg-indigo-500/20 text-[var(--indigo)] border border-indigo-500/20"
            >
              {t.walkMeThrough}
            </button>

            <button
              onClick={handleSpeak}
              title={ttsLoading ? t.ttsGenerating : ttsPlaying ? t.ttsStop : t.ttsReadAloud}
              className="ml-auto text-[var(--txa)] hover:text-[var(--tx4)] transition-colors p-1 rounded-lg hover:bg-[var(--ov1)]"
            >
              {ttsLoading ? (
                <Loader size={13} className="animate-spin text-[var(--indigo)]" />
              ) : ttsPlaying ? (
                <Square size={13} className="text-[var(--indigo)]" />
              ) : (
                <Volume2 size={13} />
              )}
            </button>
            <button
              onClick={copy}
              title={t.copy}
              className="text-[var(--txa)] hover:text-[var(--tx4)] transition-colors p-1 rounded-lg hover:bg-[var(--ov1)]"
            >
              {copied ? <Check size={13} className="text-[var(--green)]" /> : <Copy size={13} />}
            </button>
          </div>
        )}

        {showAnimateNotice && (
          <div className="text-[11px] text-[var(--tx7)] bg-[var(--ov1)] rounded-lg px-2.5 py-2 flex items-center justify-between gap-2">
            <span>{t.animateNotice}</span>
            <a
              href="https://learnx-ai.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--indigo)] font-medium whitespace-nowrap hover:underline"
            >
              {t.goToLearnX}
            </a>
          </div>
        )}

        {!isMidScaffold && (
          <div className="flex flex-wrap gap-1.5">
            {chips.map((chip, i) => (
              <button
                key={i}
                onClick={() => onChipClick?.(chip)}
                className="text-[11px] px-2.5 py-1 rounded-full border border-[var(--bd)] hover:border-[var(--bd2)] text-[var(--tx7)] hover:text-[var(--tx2)] hover:bg-[var(--ov1)]"
              >
                {chip}
              </button>
            ))}
            <button
              // Prompt text stays English on purpose, matching
              // frontend/components/chat/MessageBubble.tsx's own hardcoded
              // 'Give me a concrete real-world example of this' — the app
              // doesn't localize this prompt either, only the button label.
              onClick={() => onChipClick?.('Give me a concrete real-world example of this')}
              className="text-[11px] px-2.5 py-1 rounded-full border border-amber-500/20 hover:border-amber-500/35 text-[var(--amber)]"
            >
              {t.showExample}
            </button>
          </div>
        )}

        {!isMidScaffold && (
          <div className="flex gap-3">
            <button
              onClick={() => onSimplify?.()}
              className="text-[10px] text-[var(--tx8)] hover:text-[var(--tx4)] transition-colors"
            >
              {t.simplify}
            </button>
            <button
              onClick={() => onGoDeeper?.()}
              className="text-[10px] text-[var(--tx8)] hover:text-[var(--tx4)] transition-colors"
            >
              {t.goDeeper}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
