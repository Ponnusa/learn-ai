'use client';
import { useRef, useState, KeyboardEvent } from 'react';
import { Send, Paperclip, X, Mic, Square } from 'lucide-react';
import { useTranslation } from '@/hooks/useTranslation';
import { transcribeAudio } from '@/lib/api';

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
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const { t, language } = useTranslation();

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
    if (f.type === 'application/pdf') { onPdfOpen?.(f); return; }
    if (!f.type.startsWith('image/')) return;
    setFile(f);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunksRef.current = [];
      const mr = new MediaRecorder(stream);
      mediaRecorderRef.current = mr;
      mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.onstop = async () => {
        stream.getTracks().forEach(tr => tr.stop());
        const blob = new Blob(chunksRef.current, { type: mr.mimeType });
        setTranscribing(true);
        try {
          const result = await transcribeAudio(blob, language);
          setText(prev => prev ? `${prev} ${result}` : result);
          textRef.current?.focus();
        } catch {
          // mic permission or network issue — user can try again
        } finally {
          setTranscribing(false);
        }
      };
      mr.start();
      setRecording(true);
    } catch {
      // getUserMedia denied or unavailable
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current = null;
    setRecording(false);
  }

  return (
    <div className="px-4 pb-4 pt-2">
      {/* File preview */}
      {file && (
        <div className="flex items-center gap-2 bg-[var(--ov3)] rounded-lg px-3 py-2 mb-2 text-sm text-[var(--tx3)]">
          <Paperclip size={14} className="text-[var(--purple)]" />
          <span className="truncate flex-1">{file.name}</span>
          <button onClick={() => setFile(null)} className="text-[var(--tx6)] hover:text-[var(--tx1)]">
            <X size={14} />
          </button>
        </div>
      )}

      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`flex items-end gap-2 bg-[var(--input)] border rounded-2xl px-4 py-3 transition-colors ${
          dragOver ? 'border-purple-500' : 'border-[var(--bd)] focus-within:border-[var(--bd2)]'
        }`}
      >
        {/* Attach */}
        <input
          ref={fileRef}
          type="file"
          accept="application/pdf,image/*"
          className="hidden"
          onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        <button
          data-tour="image-upload"
          onClick={() => fileRef.current?.click()}
          className="text-[var(--tx6)] hover:text-[var(--tx2)] transition-colors shrink-0 pb-0.5"
          title="Attach PDF or image"
        >
          <Paperclip size={18} />
        </button>

        {/* Text input */}
        <textarea
          data-tour="chat-input"
          ref={textRef}
          value={transcribing ? t.chat.micTranscribing : text}
          onChange={e => { if (!transcribing) setText(e.target.value); }}
          onKeyDown={handleKey}
          placeholder={file ? t.chat.placeholderWithFile : t.chat.placeholder}
          disabled={disabled || loading || transcribing}
          rows={1}
          className="flex-1 bg-transparent text-[var(--tx1)] t-ph outline-none resize-none text-sm leading-6 max-h-40 overflow-y-auto no-scrollbar"
          style={{ minHeight: '24px' }}
        />

        {/* Mic */}
        <button
          onClick={recording ? stopRecording : startRecording}
          disabled={disabled || loading || transcribing}
          title={recording ? t.chat.micStop : t.chat.micRecord}
          className={`shrink-0 pb-0.5 transition-colors ${
            recording
              ? 'text-red-400 hover:text-red-300'
              : transcribing
                ? 'text-purple-400 animate-pulse cursor-not-allowed'
                : 'text-[var(--tx6)] hover:text-[var(--tx2)]'
          }`}
        >
          {recording ? <Square size={16} /> : <Mic size={18} />}
        </button>

        {/* Send */}
        <button
          onClick={handleSend}
          disabled={disabled || loading || (!text.trim() && !file)}
          className={`shrink-0 pb-0.5 transition-colors ${
            text.trim() || file
              ? 'text-purple-400 hover:text-purple-300'
              : 'text-[var(--txa)] cursor-not-allowed'
          }`}
        >
          <Send size={18} />
        </button>
      </div>

      <p className="text-center text-[var(--txa)] text-[10px] mt-2">
        {t.chat.disclaimer}
      </p>
    </div>
  );
}
