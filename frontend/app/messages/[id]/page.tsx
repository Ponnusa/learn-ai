'use client';
import { useEffect, useRef, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { ArrowLeft, Loader2, Send } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Message { id: string; sender_id: string; body: string; created_at: string | null; is_mine: boolean; }

export default function MessageThreadPage() {
  const router       = useRouter();
  const params       = useParams();
  const otherUserId  = params.id as string;
  const { user, token } = useSessionStore();

  const [messages, setMessages] = useState<Message[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [text,     setText]     = useState('');
  const [sending,  setSending]  = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    if (!user) { router.replace('/auth/login'); return; }
    let stopped = false;

    async function poll() {
      try {
        const res = await fetch(`${API_BASE}/api/messages/thread/${otherUserId}`, { headers: { Authorization: `Bearer ${token}` } });
        if (!stopped && res.ok) setMessages(await res.json());
      } finally {
        if (!stopped) setLoading(false);
      }
      if (!stopped) setTimeout(poll, 4000);
    }
    poll();
    return () => { stopped = true; };
  }, [user, otherUserId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  async function send() {
    const body = text.trim();
    if (!body || sending) return;
    setSending(true);
    setText('');
    try {
      await fetch(`${API_BASE}/api/messages/thread/${otherUserId}`, {
        method: 'POST', headers, body: JSON.stringify({ text: body }),
      });
      const res = await fetch(`${API_BASE}/api/messages/thread/${otherUserId}`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) setMessages(await res.json());
    } finally { setSending(false); }
  }

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );

  return (
    <div className="p-6 max-w-2xl mx-auto flex flex-col h-[calc(100vh-2rem)]">
      <button onClick={() => router.push('/messages')}
        className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm mb-4 transition-colors shrink-0">
        <ArrowLeft size={15} /> Back to messages
      </button>

      <div className="flex-1 overflow-y-auto space-y-2 mb-4 pr-1">
        {messages.length === 0 ? (
          <p className="text-[var(--tx7)] text-sm text-center py-12">No messages yet — say hello.</p>
        ) : messages.map(m => (
          <div key={m.id} className={`max-w-[80%] p-3 rounded-2xl text-sm ${
            m.is_mine ? 'bg-purple-600 text-white ml-auto' : 'bg-[var(--surface)] border border-[var(--bd)] text-[var(--tx2)]'
          }`}>
            {m.body}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <input
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') send(); }}
          placeholder="Type a message…"
          className="flex-1 bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-4 py-2.5
                     text-sm text-[var(--tx1)] outline-none focus:border-purple-500/60 transition-colors"
        />
        <button onClick={send} disabled={sending || !text.trim()}
          className="w-10 h-10 flex items-center justify-center bg-purple-600 hover:bg-purple-500
                     text-white rounded-xl transition-all disabled:opacity-40">
          {sending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
        </button>
      </div>
    </div>
  );
}
