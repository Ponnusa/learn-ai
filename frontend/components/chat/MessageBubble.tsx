'use client';
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { Copy, Check, ChevronDown, ChevronUp } from 'lucide-react';
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
  const [actionsExpanded, setActionsExpanded] = useState(true);
  const { t } = useTranslation();
  const isUser = message.role === 'user';
  const subject = message.metadata?.subject;

  function copy() {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (isUser) {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-[80%] bg-purple-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="mb-6">
      {/* AI bubble */}
      <div className="flex gap-3">
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

          {/* Content */}
          <div className="prose prose-invert prose-sm max-w-none text-white/90 leading-relaxed">
            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
              {message.content}
            </ReactMarkdown>
          </div>

          {/* Action bar */}
          <div className="mt-3 flex flex-wrap gap-2 items-center">
            <MakeVisualButton
              subject={subject?.subject ?? null}
              onClick={() => onMakeVisual?.(message.content, subject?.subject)}
            />
            <button
              onClick={() => onTestYourself?.(message.content, subject?.subject)}
              className="text-xs px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-white/70 hover:text-white transition-colors"
            >
              {t.chat.testYourself}
            </button>
            <button
              onClick={onSimplify}
              className="text-xs px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-white/50 hover:text-white/70 transition-colors"
            >
              {t.chat.simplify}
            </button>
            <button
              onClick={onGoDeeper}
              className="text-xs px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-white/50 hover:text-white/70 transition-colors"
            >
              {t.chat.goDeeper}
            </button>
            <button onClick={copy} className="ml-auto text-white/30 hover:text-white/60 transition-colors">
              {copied ? <Check size={14} /> : <Copy size={14} />}
            </button>
          </div>

          {/* Suggestion chips */}
          {message.metadata?.chips && message.metadata.chips.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {message.metadata.chips.map((chip, i) => (
                <button
                  key={i}
                  onClick={() => onChipClick?.(chip)}
                  className="text-xs px-3 py-1.5 rounded-full border border-white/15 text-white/60 hover:text-white hover:border-white/30 transition-colors"
                >
                  {chip}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
