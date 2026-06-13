'use client';
import { useState } from 'react';
import { X, Copy, Check, ChevronDown, ChevronUp } from 'lucide-react';

interface DebugData {
  model:               string;
  system_prompt:       string;
  system_prompt_chars: number;
  material_chars?:     number;
  history:             { role: string; content: string }[];
  history_count:       number;
  conversation_id:     string | null;
  subject?:            string | null;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }
  return (
    <button
      onClick={copy}
      className="flex items-center gap-1 text-[10px] text-[var(--tx6)] hover:text-[var(--tx2)] transition-colors px-2 py-0.5 rounded border border-[var(--bd)] hover:border-[var(--bd2)]"
    >
      {copied ? <Check size={10} className="text-emerald-400" /> : <Copy size={10} />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
}

function Section({ label, content, chars, sub }: { label: string; content: string; chars: number; sub?: string }) {
  const [expanded, setExpanded] = useState(false);
  const PREVIEW = 800;
  const long    = content.length > PREVIEW;
  const shown   = long && !expanded ? content.slice(0, PREVIEW) + '\n…' : content;
  const tokens  = Math.round(chars / 4);

  return (
    <div className="border border-[var(--bd)] rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 bg-[var(--ov2)] border-b border-[var(--bd)]">
        <div>
          <span className="text-[var(--tx2)] text-xs font-semibold">{label}</span>
          {sub && <span className="ml-2 text-[var(--tx6)] text-[10px]">{sub}</span>}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[var(--tx6)] text-[10px]">{chars.toLocaleString()} chars · ~{tokens.toLocaleString()} tokens</span>
          <CopyButton text={content} />
        </div>
      </div>
      <pre className="text-[11px] text-[var(--tx3)] font-mono leading-relaxed p-3 overflow-x-auto whitespace-pre-wrap break-words max-h-72 overflow-y-auto">
        {shown}
      </pre>
      {long && (
        <button
          onClick={() => setExpanded(e => !e)}
          className="w-full flex items-center justify-center gap-1 py-1.5 text-[10px] text-[var(--tx6)] hover:text-[var(--tx2)] border-t border-[var(--bd)] transition-colors"
        >
          {expanded ? <><ChevronUp size={10} /> Show less</> : <><ChevronDown size={10} /> Show all ({chars.toLocaleString()} chars)</>}
        </button>
      )}
    </div>
  );
}

export function DebugPromptModal({ data, onClose }: { data: DebugData; onClose: () => void }) {
  const historyText = data.history
    .map(m => `[${m.role.toUpperCase()}]\n${m.content}`)
    .join('\n\n---\n\n');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-2xl bg-[var(--surface)] rounded-2xl border border-[var(--bd)] shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--bd)] shrink-0">
          <div>
            <h2 className="text-[var(--tx1)] font-semibold text-sm">Prompt Debug</h2>
            <p className="text-[var(--tx6)] text-[11px] mt-0.5">
              Model: <span className="text-purple-400 font-mono">{data.model}</span>
              {data.subject && <> · Subject: <span className="text-[var(--tx3)]">{data.subject}</span></>}
              {data.conversation_id && <> · Conv: <span className="text-[var(--tx6)] font-mono">{data.conversation_id.slice(0, 8)}…</span></>}
            </p>
          </div>
          <button onClick={onClose} className="text-[var(--tx6)] hover:text-[var(--tx1)] transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <Section
            label="System Prompt"
            content={data.system_prompt}
            chars={data.system_prompt_chars}
            sub={data.material_chars ? `(incl. ${(data.material_chars / 1000).toFixed(0)}k chars of material)` : undefined}
          />

          <div className="border border-[var(--bd)] rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-3 py-2 bg-[var(--ov2)] border-b border-[var(--bd)]">
              <span className="text-[var(--tx2)] text-xs font-semibold">
                Message History
                <span className="ml-2 text-[var(--tx6)] font-normal">({data.history_count} messages)</span>
              </span>
              {historyText && <CopyButton text={historyText} />}
            </div>
            {data.history.length === 0 ? (
              <p className="text-[var(--tx6)] text-xs p-3 italic">No history yet — first message in this conversation.</p>
            ) : (
              <div className="divide-y divide-[var(--bd)] max-h-64 overflow-y-auto">
                {data.history.map((m, i) => (
                  <div key={i} className="px-3 py-2">
                    <span className={`text-[10px] font-semibold uppercase tracking-wider ${
                      m.role === 'user' ? 'text-purple-400' : 'text-emerald-400'
                    }`}>
                      {m.role}
                    </span>
                    <pre className="text-[11px] text-[var(--tx3)] font-mono mt-1 whitespace-pre-wrap break-words line-clamp-4">
                      {m.content.slice(0, 400)}{m.content.length > 400 ? '…' : ''}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
