'use client';
import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Sidebar } from '@/components/layout/Sidebar';
import { InputBar } from '@/components/chat/InputBar';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { ThinkingIndicator } from '@/components/chat/ThinkingIndicator';
import dynamic from 'next/dynamic';

// react-pdf uses browser-only APIs (canvas, PDF.js worker) — never SSR
const PDFViewerModal = dynamic(
  () => import('@/components/chat/PDFViewerModal').then(m => m.PDFViewerModal),
  { ssr: false, loading: () => null },
);
import { SignupModal } from '@/components/gates/SignupModal';
import { useTranslation } from '@/hooks/useTranslation';
import { useSessionStore } from '@/store/sessionStore';
import { sendMessage, createSession, generateVideo, generateQuiz, uploadFile, listConversations, getMessages } from '@/lib/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  metadata?: { chips?: string[]; subject?: any; imageUrl?: string };
}

export default function HomePage() {
  const [messages, setMessages]           = useState<Message[]>([]);
  const [loading, setLoading]             = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [currentSubject, setCurrentSubject] = useState<any>(null);
  const [showSignup, setShowSignup]       = useState(false);
  const [signupReason, setSignupReason]   = useState<'session_limit' | 'soft_nudge'>('soft_nudge');
  const [conversations, setConversations] = useState<any[]>([]);
  const [pdfFile, setPdfFile]             = useState<File | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const router    = useRouter();
  const { t }     = useTranslation();
  const { sessionId, setSessionId, msgCount, user, token, incrementMsg,
          activeConversationId, setActiveConversationId } = useSessionStore();

  // Init anonymous session
  useEffect(() => {
    if (!sessionId && !user) {
      createSession().then(s => setSessionId(s.session_id)).catch(() => {});
    }
  }, []);

  // Load conversation list whenever auth state settles
  useEffect(() => {
    if (user?.id) {
      listConversations(user.id, undefined, token ?? undefined)
        .then(setConversations)
        .catch(() => {});
    } else if (sessionId) {
      listConversations(undefined, sessionId)
        .then(setConversations)
        .catch(() => {});
    }
  }, [user?.id, sessionId]);

  // Restore the last active conversation after page navigation
  useEffect(() => {
    if (activeConversationId && !conversationId) {
      handleConversationSelect(activeConversationId);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeConversationId]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Dismiss any signup modal the moment the user becomes logged-in
  useEffect(() => {
    if (user) setShowSignup(false);
  }, [user]);

  // Soft nudge after 4th message (anonymous only)
  useEffect(() => {
    if (!user && msgCount === 4) {
      setSignupReason('soft_nudge');
      setShowSignup(true);
    }
  }, [msgCount, user]);

  // Load an existing conversation when clicked in the sidebar
  async function handleConversationSelect(id: string) {
    if (id === conversationId) return;
    setConversationId(id);
    setActiveConversationId(id);
    setMessages([]);
    try {
      const rows = await getMessages(id, token ?? undefined);
      setMessages(rows.map((m: any) => ({
        id:       m.id,
        role:     m.role as 'user' | 'assistant',
        content:  m.content,
        metadata: m.metadata ?? undefined,
      })));
      const conv = conversations.find(c => c.id === id);
      if (conv?.subject) setCurrentSubject({ subject: conv.subject, subtopic: conv.subtopic });
    } catch { /* silently ignore */ }
  }

  async function handleSend(text: string, file?: File) {
    if (!text && !file) return;

    // Hard gate at anonymous limit
    if (!user && msgCount >= 8) {
      setSignupReason('session_limit');
      setShowSignup(true);
      return;
    }

    setMessages(prev => [...prev, { id: Date.now().toString(), role: 'user', content: text }]);
    setLoading(true);
    incrementMsg();

    try {
      const res = await sendMessage({
        message: text,
        conversation_id: conversationId ?? undefined,
        user_id:   user?.id,
        session_id: sessionId ?? undefined,
        language:  'en',
      }, token ?? undefined);

      setConversationId(res.conversation_id);
      setActiveConversationId(res.conversation_id);
      if (res.subject?.subject) setCurrentSubject(res.subject);

      // Add newly-created conversation to the sidebar list
      if (!conversationId) {
        setConversations(prev => {
          const exists = prev.some(c => c.id === res.conversation_id);
          if (exists) return prev;
          return [{
            id:         res.conversation_id,
            title:      text.slice(0, 60),
            subject:    res.subject?.subject,
            subtopic:   res.subject?.subtopic,
            updated_at: new Date().toISOString(),
          }, ...prev];
        });
      }

      setMessages(prev => [...prev, {
        id:       res.message_id,
        role:     'assistant',
        content:  res.reply,
        metadata: { chips: res.chips, subject: res.subject },
      }]);
    } catch (e: any) {
      const isLimit = e.message === 'session_limit_reached' || e.message === 'Daily message limit reached';
      if (isLimit && !user) {
        // Anonymous user hit their limit — show the signup gate
        setSignupReason('session_limit');
        setShowSignup(true);
      } else if (isLimit && user) {
        // Logged-in user got a limit error — show inline, never block the UI
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: `⚠️ **Daily message limit reached.** You've used all your messages for today. Come back tomorrow or upgrade your plan.`,
        }]);
      } else {
        // Show error inline so the user knows something went wrong
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: `⚠️ **Something went wrong.** ${e.message && e.message !== 'Request failed' ? e.message : 'Please try again in a moment.'}`,
        }]);
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleMakeVisual(content: string, subject?: string) {
    if (!user && msgCount >= 8) { setSignupReason('session_limit'); setShowSignup(true); return; }
    try {
      const res = await generateVideo({
        prompt: content,
        conversation_id: conversationId ?? undefined,
        user_id:   user?.id,
        session_id: sessionId ?? undefined,
        subject:   subject ?? currentSubject?.subject,
      }, token ?? undefined);

      if (!res.supported) {
        setMessages(prev => [...prev, { id: Date.now().toString(), role: 'assistant', content: `🎬 ${res.message}` }]);
        return;
      }
      router.push(`/videos?id=${res.video_id}`);
    } catch (e) { console.error(e); }
  }

  async function handleTestYourself(content: string, subject?: string) {
    // Show a "generating quiz…" indicator in the chat
    const loadingId = Date.now().toString();
    setMessages(prev => [...prev, {
      id: loadingId,
      role: 'assistant',
      content: '✏️ Generating your quiz…',
    }]);
    setLoading(true);

    try {
      const res = await generateQuiz({
        topic: content.slice(0, 300),
        conversation_id: conversationId ?? undefined,
        user_id:         user?.id,
        session_id:      sessionId ?? undefined,
        subject:         subject ?? currentSubject?.subject,
      }, token ?? undefined);

      // Remove the loading message
      setMessages(prev => prev.filter(m => m.id !== loadingId));

      if (!res.questions || res.questions.length === 0) {
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: '⚠️ Quiz generation returned no questions. Please try again.',
        }]);
        return;
      }

      // Save questions to localStorage so the quiz page can read them quickly
      localStorage.setItem(`quiz_${res.quiz_id}`, JSON.stringify(res.questions));
      router.push(`/quiz/${res.quiz_id}`);
    } catch (e: any) {
      setMessages(prev => prev.filter(m => m.id !== loadingId));
      const msg = e?.message;
      if (msg === 'session_limit_reached' || msg === 'Daily quiz limit reached') {
        setSignupReason('session_limit');
        setShowSignup(true);
      } else {
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: `⚠️ **Couldn't generate quiz.** ${msg && msg !== 'Request failed' ? msg : 'Please try again in a moment.'}`,
        }]);
      }
    } finally {
      setLoading(false);
    }
  }

  async function handlePdfAsk(question: string, context: { text?: string; imageDataUrl?: string }) {
    setPdfFile(null); // close modal immediately

    if (!user && msgCount >= 8) {
      setSignupReason('session_limit');
      setShowSignup(true);
      return;
    }

    // ── Upload region image to R2 (falls back to base64 if R2 not configured) ─
    let imageUrl: string | undefined;
    let apiImageUrl: string | undefined;

    if (context.imageDataUrl) {
      try {
        // Convert base64 data URL → File → upload to R2
        const fetchRes  = await fetch(context.imageDataUrl);
        const blob      = await fetchRes.blob();
        const imgFile   = new File([blob], `pdf-region-${Date.now()}.png`, { type: 'image/png' });
        const uploaded  = await uploadFile(imgFile, sessionId ?? undefined, user?.id, token ?? undefined) as { url: string };
        imageUrl    = uploaded.url;   // persistent R2 URL shown in chat
        apiImageUrl = uploaded.url;   // sent to OpenAI
      } catch {
        // R2 not configured or upload failed — use base64 as fallback
        // base64 data URLs work fine with OpenAI vision, just won't persist
        imageUrl    = context.imageDataUrl;
        apiImageUrl = context.imageDataUrl;
      }
    }

    // ── Build user message (text shown in bubble) ────────────────────────────
    const userText = context.text
      ? `${question}\n\n---\n*Context from PDF:*\n"${context.text}"`
      : question;

    setMessages(prev => [...prev, {
      id:       Date.now().toString(),
      role:     'user',
      content:  userText,
      metadata: { imageUrl },          // shows image thumbnail in bubble
    }]);
    setLoading(true);
    incrementMsg();

    try {
      const apiMessage = context.text
        ? `${question}\n\nContext from PDF:\n${context.text}`
        : question;

      const res = await sendMessage({
        message:         apiMessage,
        image_url:       apiImageUrl,
        conversation_id: conversationId ?? undefined,
        user_id:         user?.id,
        session_id:      sessionId ?? undefined,
        language:        'en',
      }, token ?? undefined);

      setConversationId(res.conversation_id);
      if (res.subject?.subject) setCurrentSubject(res.subject);

      // Add newly-created conversation to the sidebar list (PDF ask)
      if (!conversationId) {
        setConversations(prev => {
          const exists = prev.some(c => c.id === res.conversation_id);
          if (exists) return prev;
          return [{
            id:         res.conversation_id,
            title:      question.slice(0, 60),
            subject:    res.subject?.subject,
            subtopic:   res.subject?.subtopic,
            updated_at: new Date().toISOString(),
          }, ...prev];
        });
      }

      setMessages(prev => [...prev, {
        id:       res.message_id,
        role:     'assistant',
        content:  res.reply,
        metadata: { chips: res.chips, subject: res.subject },
      }]);
    } catch (e: any) {
      const isLimit = e.message === 'session_limit_reached' || e.message === 'Daily message limit reached';
      if (isLimit && !user) {
        setSignupReason('session_limit');
        setShowSignup(true);
      } else if (isLimit && user) {
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: `⚠️ **Daily message limit reached.** Come back tomorrow or upgrade your plan.`,
        }]);
      } else {
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: `⚠️ **Something went wrong.** ${e.message && e.message !== 'Request failed' ? e.message : 'Please try again in a moment.'}`,
        }]);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        conversations={conversations}
        selectedConversationId={conversationId ?? undefined}
        onNewChat={() => { setMessages([]); setConversationId(null); setActiveConversationId(null); }}
        onConversationSelect={handleConversationSelect}
      />

      <main className="flex-1 flex flex-col min-w-0 bg-[#0f0f0f]">
        <div className="flex-1 overflow-y-auto px-4 py-6">
          <div className="max-w-2xl mx-auto">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center text-white text-2xl font-bold mb-6 shadow-lg shadow-purple-500/20">
                  L
                </div>
                <h1 className="text-2xl font-bold text-white mb-2">{t.chat.welcomeTitle}</h1>
                <p className="text-white/50 text-sm mb-8">{t.chat.welcomeSubtitle}</p>
                <div className="flex flex-wrap gap-2 justify-center max-w-lg">
                  {t.chat.starterPrompts.map((p, i) => (
                    <button key={i} onClick={() => handleSend(p)}
                      className="px-4 py-2.5 rounded-xl bg-[#1a1a1a] hover:bg-[#222] border border-white/10 hover:border-white/20 text-white/80 hover:text-white text-sm transition-all shadow-sm">
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map(msg => (
                <MessageBubble key={msg.id} message={msg}
                  onChipClick={handleSend}
                  onMakeVisual={handleMakeVisual}
                  onTestYourself={handleTestYourself}
                  onSimplify={() => handleSend('Can you simplify that explanation?')}
                  onGoDeeper={() => handleSend('Can you go deeper on that?')}
                />
              ))
            )}

            {loading && <ThinkingIndicator />}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* Credit warning */}
        {!user && msgCount >= 6 && (
          <div className="text-center py-2 text-xs text-amber-400/80 bg-amber-400/5 border-t border-amber-400/10">
            {t.credits.messagesLeft.replace('{n}', String(8 - msgCount))}
            {' · '}
            <button onClick={() => setShowSignup(true)} className="underline hover:text-amber-300">
              {t.credits.upgradeToKeepLearning}
            </button>
          </div>
        )}

        <InputBar onSend={handleSend} onPdfOpen={f => setPdfFile(f)} loading={loading} />
      </main>

      {pdfFile && (
        <PDFViewerModal
          file={pdfFile}
          onClose={() => setPdfFile(null)}
          onAsk={handlePdfAsk}
        />
      )}

      {showSignup && (
        <SignupModal
          reason={signupReason}
          onClose={signupReason === 'soft_nudge' ? () => setShowSignup(false) : undefined}
          savedItems={messages.length > 0 ? [
            `Conversation (${messages.filter(m => m.role === 'user').length} messages)`,
            ...(currentSubject?.subject ? [`Subject: ${currentSubject.subject}`] : []),
          ] : []}
        />
      )}
    </div>
  );
}
