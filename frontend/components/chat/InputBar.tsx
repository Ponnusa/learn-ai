'use client';
import { useRef, useState, KeyboardEvent } from 'react';
import { Send, Paperclip, Image, X } from 'lucide-react';
import { useTranslation } from '@/hooks/useTranslation';

interface InputBarProps {
  onSend: (text: string, file?: File) => void;
  onPdfOpen?: (file: File) => void;
  loading?: boolean;
  hasFile?: boolean;
  disabled?: boolean;
}

export function InputBar({ onSend, onPdfOpen, loading = false, hasFile = false, disabled = false }: InputBarProps) {
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const { t } = useTranslation();

  function handleSend() {
    if (!text.trim() && !file) return;
    onSend(text.trim(), file ?? undefined);
    setText('');
    setFile(null);
  }

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleFile(f: File) {
    if (!f) return;
    if (f.type === 'application/pdf') {
      // PDFs open in the viewer modal instead of being attached
      onPdfOpen?.(f);
      return;
    }
    if (!f.type.startsWith('image/')) return;
    setFile(f);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }

  return (
    <div className="px-4 pb-4 pt-2">
      {/* Dropped file preview */}
      {file && (
        <div className="flex items-center gap-2 bg-white/10 rounded-lg px-3 py-2 mb-2 text-sm text-white/80">
          <Paperclip size={14} className="text-purple-400" />
          <span className="truncate flex-1">{file.name}</span>
          <button onClick={() => setFile(null)} className="text-white/40 hover:text-white">
            <X size={14} />
          </button>
        </div>
      )}

      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`flex items-end gap-2 bg-[#1e1e1e] border rounded-2xl px-4 py-3 transition-colors ${
          dragOver ? 'border-purple-500' : 'border-white/10 focus-within:border-white/30'
        }`}
      >
        {/* Attach buttons */}
        <input
          ref={fileRef}
          type="file"
          accept="application/pdf,image/*"
          className="hidden"
          onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        <button
          onClick={() => fileRef.current?.click()}
          className="text-white/40 hover:text-white/80 transition-colors shrink-0 pb-0.5"
          title="Attach PDF or image"
        >
          <Paperclip size={18} />
        </button>

        {/* Text input */}
        <textarea
          ref={textRef}
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKey}
          placeholder={file ? t.chat.placeholderWithFile : t.chat.placeholder}
          disabled={disabled || loading}
          rows={1}
          className="flex-1 bg-transparent text-white placeholder-white/30 outline-none resize-none text-sm leading-6 max-h-40 overflow-y-auto"
          style={{ minHeight: '24px' }}
        />

        {/* Send button */}
        <button
          onClick={handleSend}
          disabled={disabled || loading || (!text.trim() && !file)}
          className={`shrink-0 pb-0.5 transition-colors ${
            text.trim() || file
              ? 'text-purple-400 hover:text-purple-300'
              : 'text-white/20 cursor-not-allowed'
          }`}
        >
          <Send size={18} />
        </button>
      </div>

      <p className="text-center text-white/20 text-[10px] mt-2">
        Learn-AI can make mistakes — verify important information.
      </p>
    </div>
  );
}
