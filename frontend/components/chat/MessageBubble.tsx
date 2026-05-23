'use client';
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { Copy, Check } from 'lucide-react';
import { useTranslation } from '@/hooks/useTranslation';
import { SubjectBadge } from './SubjectBadge';
import { MakeVisualButton } from './MakeVisualButton';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  metadata?: {
    chips?: string[];
    subject?: { subject: string; subtopic: string; icon: string };
  };
}

interface MessageBubbleProps {
  message: Message;
  onChipClick?: (chip: string) => void;
  onMakeVisual?: (content: string, subject?: string) => void;
  onTestYourself?: (content: string, subject?: string) => void;
  onSimplify?: () => void;
  onGoDeeper?: () => void;
}

export function MessageBubble({
  message, onChipClick, onMakeVisual, onTestYourself, onSimplify, onGoDeeper,
}: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const { t } = useTranslation();
  const isUser  = message.role === 'user';
  const subject = message.metadata?.subject;
  const aiChips = message.metadata?.chips ?? [];

  function copy() {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  /* ── User bubble ──────────────────────────────────────────────── */
  if (isUser) {
    return (
      <div className="flex justify-end mb-5">
        <div
          className="max-w-[78%] rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed text-white font-medium shadow-md shadow-purple-900/30"
          style={{ background: 'linear-gradient(135deg,#7c3aed,#6d28d9)' }}
        >
          {message.content}
        </div>
      </div>
    );
  }

  /* ── AI bubble ────────────────────────────────────────────────── */
  return (
    <div className="flex gap-3 mb-6 items-start">
      {/* Avatar */}
      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-purple-500 to-blue-500
                      flex items-center justify-center text-white text-xs font-bold shrink-0 mt-1">
        AI
      </div>

      <div className="flex-1 min-w-0">
        {/* Subject badge */}
        {subject?.subject && (
          <div className="mb-2">
            <SubjectBadge subject={subject.subject} subtopic={subject.subtopic} />
          </div>
        )}

        {/* Message card */}
        <div className="rounded-2xl rounded-tl-sm bg-[#1a1a1a] border border-white/[0.09]
                        shadow-lg shadow-black/30 px-5 py-4">
          {/* Prose content — uses .ai-content from globals.css for reliable dark-mode colors */}
          <div className="ai-content">
            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
              {message.content}
            </ReactMarkdown>
          </div>

          {/* Divider */}
          <div className="mt-4 pt-3 border-t border-white/[0.06]">
            {/* Primary actions */}
            <div className="flex flex-wrap gap-2 items-center">
              <MakeVisualButton
                subject={subject?.subject ?? null}
                onClick={() => onMakeVisual?.(message.content, subject?.subject)}
              />
              <button
                onClick={() => onTestYourself?.(message.content, subject?.subject)}
                className="text-xs px-3 py-1.5 rounded-lg flex items-center gap-1.5 font-medium transition-all
                           bg-indigo-600/20 hover:bg-indigo-600/35 text-indigo-300 hover:text-indigo-200
                           border border-indigo-500/25"
              >
                ✏️ Quiz me
              </button>

              {/* Copy — pushed to right */}
              <button
                onClick={copy}
                title="Copy"
                className="ml-auto text-white/25 hover:text-white/60 transition-colors p-1 rounded-lg hover:bg-white/5"
              >
                {copied
                  ? <Check size={14} className="text-green-400" />
                  : <Copy size={14} />}
              </button>
            </div>

            {/* Suggestion chips */}
            <div className="mt-3 flex flex-wrap gap-2">
              {aiChips.map((chip, i) => (
                <button
                  key={i}
                  onClick={() => onChipClick?.(chip)}
                  className="text-xs px-3 py-1.5 rounded-full transition-all
                             border border-white/10 hover:border-white/25
                             text-white/55 hover:text-white/90 hover:bg-white/5"
                >
                  {chip}
                </button>
              ))}
              {/* Always-shown example chip */}
              <button
                onClick={() => onChipClick?.('Give me a concrete real-world example of this')}
                className="text-xs px-3 py-1.5 rounded-full transition-all
                           border border-amber-500/20 hover:border-amber-500/40
                           text-amber-400/70 hover:text-amber-300"
              >
                💡 Show me an example
              </button>
            </div>

            {/* Tertiary actions */}
            <div className="mt-3 flex gap-4">
              <button
                onClick={onSimplify}
                className="text-[11px] text-white/30 hover:text-white/60 transition-colors flex items-center gap-1"
              >
                <span>↓</span> {t.chat.simplify}
              </button>
              <button
                onClick={onGoDeeper}
                className="text-[11px] text-white/30 hover:text-white/60 transition-colors flex items-center gap-1"
              >
                <span>↑</span> {t.chat.goDeeper}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
