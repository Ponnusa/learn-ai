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

  function copy() {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  // ── User bubble ────────────────────────────────────────────────────────────
  if (isUser) {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-[80%] bg-purple-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed">
          {message.content}
        </div>
      </div>
    );
  }

  const aiChips = message.metadata?.chips ?? [];

  // ── AI bubble ──────────────────────────────────────────────────────────────
  return (
    <div className="mb-8">
      <div className="flex gap-3">
        {/* Avatar */}
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center text-white text-xs font-bold shrink-0 mt-0.5">
          AI
        </div>

        <div className="flex-1 min-w-0">
          {/* Subject badge */}
          {subject?.subject && (
            <div className="mb-2">
              <SubjectBadge subject={subject.subject} subtopic={subject.subtopic} />
            </div>
          )}

          {/* Content — remark-math + rehype-katex renders $...$ and $$...$$ */}
          <div className="prose prose-invert prose-sm max-w-none text-white/90 leading-relaxed
                          prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5
                          prose-headings:text-white prose-strong:text-white
                          prose-code:text-purple-300 prose-code:bg-white/10 prose-code:px-1 prose-code:rounded">
            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
              {message.content}
            </ReactMarkdown>
          </div>

          {/* ── Primary action buttons ── */}
          <div className="mt-4 flex flex-wrap gap-2">
            {/* Create Video */}
            <MakeVisualButton
              subject={subject?.subject ?? null}
              onClick={() => onMakeVisual?.(message.content, subject?.subject)}
            />

            {/* Quiz me */}
            <button
              onClick={() => onTestYourself?.(message.content, subject?.subject)}
              className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 hover:text-indigo-200 transition-colors border border-indigo-500/30 flex items-center gap-1.5"
            >
              ✏️ {t.chat.testYourself}
            </button>

            {/* Spacer + copy */}
            <button
              onClick={copy}
              className="ml-auto text-white/30 hover:text-white/60 transition-colors p-1"
              title="Copy response"
            >
              {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
            </button>
          </div>

          {/* ── Suggestion chips (AI-generated + always-shown example chip) ── */}
          <div className="mt-3 flex flex-wrap gap-2">
            {/* AI-generated topic-specific chips */}
            {aiChips.map((chip, i) => (
              <button
                key={i}
                onClick={() => onChipClick?.(chip)}
                className="text-xs px-3 py-1.5 rounded-full border border-white/15 hover:border-white/30 text-white/60 hover:text-white transition-colors"
              >
                {chip}
              </button>
            ))}

            {/* Always-shown: "Show me an example" */}
            <button
              onClick={() => onChipClick?.('Give me a concrete real-world example of this')}
              className="text-xs px-3 py-1.5 rounded-full border border-white/15 hover:border-white/30 text-white/60 hover:text-white transition-colors"
            >
              💡 Show me an example
            </button>
          </div>

          {/* ── Tertiary actions ── */}
          <div className="mt-2 flex gap-3">
            <button
              onClick={onSimplify}
              className="text-xs text-white/30 hover:text-white/60 transition-colors"
            >
              ↓ {t.chat.simplify}
            </button>
            <button
              onClick={onGoDeeper}
              className="text-xs text-white/30 hover:text-white/60 transition-colors"
            >
              ↑ {t.chat.goDeeper}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
