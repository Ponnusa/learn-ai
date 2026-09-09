import { useEffect, useRef, useState } from 'react';
import { createOrGetSession, sendMessage } from '../lib/api';
import { LadderWidget } from '../components/LadderWidget';
import { EurekaBurst, EUREKA_BURST_DURATION } from '../components/EurekaBurst';
import { GenieMessage, type GenieMessageData } from './GenieMessage';

const SESSION_STORAGE_KEY = 'genie_session_id';

interface PendingSelection {
  text: string;
  pageTitle: string;
  pageUrl: string;
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<GenieMessageData[]>([]);
  const [input, setInput] = useState('');
  const [selection, setSelection] = useState<PendingSelection | null>(null);
  const [loading, setLoading] = useState(false);
  const [limitReached, setLimitReached] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Same climbing/eureka state machine as frontend/app/page.tsx's
  // updateLadderState — see that file's comments for why steps are
  // tracked via a ref (sync, not stale inside the async send handler)
  // alongside mirrored state (to trigger re-renders).
  const ladderRef = useRef({ active: false, steps: 0 });
  const [ladderPhase, setLadderPhase] = useState<'idle' | 'climbing' | 'eureka'>('idle');
  const [ladderSteps, setLadderSteps] = useState(0);
  const [eurekaBurst, setEurekaBurst] = useState(false);

  // ── Bootstrap: session + any selection that triggered opening the panel ──
  useEffect(() => {
    chrome.storage.local.get(SESSION_STORAGE_KEY).then(async (stored) => {
      try {
        const res = await createOrGetSession(stored[SESSION_STORAGE_KEY] ?? null);
        setSessionId(res.session_id);
        await chrome.storage.local.set({ [SESSION_STORAGE_KEY]: res.session_id });
      } catch {
        setError("Couldn't reach LearnX. Check your connection and try again.");
      }
    });

    chrome.runtime.sendMessage({ type: 'GENIE_GET_PENDING_SELECTION' }).then((pending) => {
      if (pending) setSelection(pending);
    });

    const listener = (message: { type: string } & PendingSelection) => {
      if (message?.type === 'GENIE_SELECTION_FORWARD') setSelection(message);
    };
    chrome.runtime.onMessage.addListener(listener);
    return () => chrome.runtime.onMessage.removeListener(listener);
  }, []);

  function updateLadderState(newDepth: number | null | undefined) {
    const waiting = (newDepth ?? 0) > 0;
    if (waiting) {
      const steps = ladderRef.current.active ? ladderRef.current.steps + 1 : 1;
      ladderRef.current = { active: true, steps };
      setLadderSteps(steps);
      setLadderPhase('climbing');
    } else {
      const wasActive = ladderRef.current.active;
      ladderRef.current = { active: false, steps: 0 };
      if (wasActive) {
        setLadderPhase('eureka');
        setTimeout(() => setLadderPhase('idle'), EUREKA_BURST_DURATION);
        setEurekaBurst(true);
        setTimeout(() => setEurekaBurst(false), EUREKA_BURST_DURATION);
      } else {
        setLadderPhase('idle');
      }
    }
  }

  async function handleSend(text: string) {
    if (!text.trim() || loading || limitReached || !sessionId) return;
    setError(null);
    setInput('');
    setSelection(null);

    const userMsg: GenieMessageData = { id: `local-${Date.now()}`, role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await sendMessage({
        message: text,
        conversation_id: conversationId ?? undefined,
        session_id: sessionId,
        source: 'extension',
      });
      setConversationId(res.conversation_id);
      updateLadderState(res.ladder_depth);
      setMessages((prev) => [...prev, { id: res.message_id, role: 'assistant', content: res.reply }]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Request failed';
      if (msg === 'session_limit_reached') {
        setLimitReached(true);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center gap-2 px-4 py-3 border-b border-[var(--bd)]">
        <span className="text-lg">🧞</span>
        <span className="font-semibold text-[var(--tx1)] text-sm">LearnX Genie</span>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-3">
        {messages.length === 0 && !selection && (
          <p className="text-sm text-[var(--tx7)] leading-relaxed">
            Select some text on any page, then click "✨ Ask LearnX" — or just type a question below.
          </p>
        )}
        {messages.map((m) => (
          <GenieMessage key={m.id} message={m} />
        ))}
        {loading && <p className="text-xs text-[var(--tx7)]">Thinking…</p>}
        {error && <p className="text-xs text-[var(--red)]">{error}</p>}
      </div>

      {selection && (
        <div className="mx-4 mb-2 p-2.5 rounded-xl border border-[var(--bd)] bg-[var(--surface)]">
          <p className="text-xs text-[var(--tx7)] mb-2 line-clamp-2">"{selection.text}"</p>
          <div className="flex gap-2">
            <button
              className="text-xs font-medium px-2.5 py-1.5 rounded-lg bg-[var(--indigo)] text-white"
              onClick={() => handleSend(`Explain this: "${selection.text}"`)}
            >
              Explain this
            </button>
            <button
              className="text-xs font-medium px-2.5 py-1.5 rounded-lg border border-[var(--bd)] text-[var(--tx2)]"
              onClick={() => handleSend(`Help me understand this: "${selection.text}"`)}
            >
              Help me understand it
            </button>
          </div>
        </div>
      )}

      {limitReached ? (
        <div className="m-4 p-3 rounded-xl border border-[var(--bd)] bg-[var(--surface)] text-center">
          <p className="text-sm text-[var(--tx2)]">You've reached the free limit for this session.</p>
          <p className="text-xs text-[var(--tx7)] mt-1">Sign in to LearnX to keep going.</p>
        </div>
      ) : (
        <form
          className="flex items-center gap-2 p-3 border-t border-[var(--bd)]"
          onSubmit={(e) => {
            e.preventDefault();
            handleSend(input);
          }}
        >
          <input
            className="flex-1 rounded-lg border border-[var(--bd)] bg-[var(--input)] text-[var(--tx1)] text-sm px-3 py-2 outline-none"
            placeholder="Ask a question…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
          <button
            type="submit"
            className="text-sm font-medium px-3 py-2 rounded-lg bg-[var(--indigo)] text-white disabled:opacity-50"
            disabled={loading || !input.trim()}
          >
            Send
          </button>
        </form>
      )}

      <LadderWidget phase={ladderPhase} steps={ladderSteps} />
      <EurekaBurst active={eurekaBurst} />
    </div>
  );
}
