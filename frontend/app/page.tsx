'use client';
import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Sidebar } from '@/components/layout/Sidebar';
import { InputBar } from '@/components/chat/InputBar';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { ThinkingIndicator } from '@/components/chat/ThinkingIndicator';
import { PDFViewerModal } from '@/components/chat/PDFViewerModal';
import { SignupModal } from '@/components/gates/SignupModal';
import { useTranslation } from '@/hooks/useTranslation';
import { useSessionStore } from '@/store/sessionStore';
import { sendMessage, createSession, generateVideo, generateQuiz } from '@/lib/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  metadata?: { chips?: string[]; subject?: any };
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
  const { sessionId, setSessionId, msgCount, user, token, incrementMsg } = useSessionStore();

  // Init anonymous session
  useEffect(() => {
    if (!sessionId && !user) {
      createSession().then(s => setSessionId(s.session_id)).catch(() => {});
    }
  }, []);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Soft nudge after 4th message
  useEffect(() => {
    if (!user && msgCount === 4) {
      setSignupReason('soft_nudge');
      setShowSignup(true);
    }
  }, [msgCount, user]);

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
      if (res.subject?.subject) setCurrentSubject(res.subject);

      setMessages(prev => [...prev, {
        id:       res.message_id,
        role:     'assistant',
        content:  res.reply,
        metadata: { chips: res.chips, subject: res.subject },
      }]);
    } catch (e: any) {
      if (e.message === 'session_limit_reached') {
        setSignupReason('session_limit');
        setShowSignup(true);
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
    try {
      const res = await generateQuiz({
        topic: content.slice(0, 300),
        conversation_id: conversationId ?? undefined,
        user_id:   user?.id,
        session_id: sessionId ?? undefined,
        subject:   subject ?? currentSubject?.subject,
      }, token ?? undefined);
      // Save questions to localStorage so the quiz page can read them
      localStorage.setItem(`quiz_${res.quiz_id}`, JSON.stringify(res.questions));
      router.push(`/quiz/${res.quiz_id}`);
    } catch (e) { console.error(e); }
  }

  async function handlePdfAsk(question: string, context: { text?: string; imageDataUrl?: string }) {
    setPdfFile(null); // close modal

    if (!user && msgCount >= 8) {
      setSignupReason('session_limit');
      setShowSignup(true);
      return;
    }

    // Build the outgoing user message text
    const userText = context.text
      ? `${question}\n\n---\n*Context from PDF:*\n"${context.text}"`
      : question;

    setMessages(prev => [...prev, { id: Date.now().toString(), role: 'user', content: userText }]);
    setLoading(true);
    incrementMsg();

    try {
      // Text context → append to message; image context → send as image_url (base64 data URL)
      const apiMessage = context.text
        ? `${question}\n\nContext from PDF:\n${context.text}`
        : question;

      const res = await sendMessage({
        message:         apiMessage,
        image_url:       context.imageDataUrl ?? undefined,
        conversation_id: conversationId ?? undefined,
        user_id:         user?.id,
        session_id:      sessionId ?? undefined,
        language:        'en',
      }, token ?? undefined);

      setConversationId(res.conversation_id);
      if (res.subject?.subject) setCurrentSubject(res.subject);

      setMessages(prev => [...prev, {
        id:       res.message_id,
        role:     'assistant',
        content:  res.reply,
        metadata: { chips: res.chips, subject: res.subject },
      }]);
    } catch (e: any) {
      if (e.message === 'session_limit_reached') {
        setSignupReason('session_limit');
        setShowSignup(true);
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
      <Sidebar conversations={conversations} onNewChat={() => { setMessages([]); setConversationId(null); }} />

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
