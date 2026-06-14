'use client';
import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Sidebar, MobileTopBar } from '@/components/layout/Sidebar';
import { InputBar } from '@/components/chat/InputBar';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { WelcomeScreen } from '@/components/chat/WelcomeScreen';
import { ThinkingIndicator } from '@/components/chat/ThinkingIndicator';
import dynamic from 'next/dynamic';

// react-pdf uses browser-only APIs (canvas, PDF.js worker) — never SSR
const PDFViewerModal = dynamic(
  () => import('@/components/chat/PDFViewerModal').then(m => m.PDFViewerModal),
  { ssr: false, loading: () => null },
);
import { SignupModal } from '@/components/gates/SignupModal';
import { useTranslation } from '@/hooks/useTranslation';
import { useLanguageStore } from '@/store/languageStore';
import { useSessionStore } from '@/store/sessionStore';
import { sendMessage, createSession, generateVideo, generateQuiz, uploadFile, getMessages, getConversationVideos, generateEduImage, listEduImages, debugChatPrompt, getStudentProfile, uploadRegionImage } from '@/lib/api';
import { DebugPromptModal } from '@/components/chat/DebugPromptModal';
import { ProfileNudgeCard } from '@/components/profile/ProfileNudgeCard';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  metadata?: {
    chips?: string[];
    subject?: any;
    imageUrl?: string;
    quiz_id?: string;
    quiz_topic?: string;
    num_questions?: number;
  };
}

export default function HomePage() {
  const [messages, setMessages]             = useState<Message[]>([]);
  const [loading, setLoading]               = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [currentSubject, setCurrentSubject] = useState<any>(null);
  const [showSignup, setShowSignup]         = useState(false);
  const [signupReason, setSignupReason]     = useState<'session_limit' | 'soft_nudge'>('soft_nudge');
  const [pdfFile, setPdfFile]               = useState<File | null>(null);
  /** Maps message ID → video ID so we can show inline status per message */
  const [videoByMsgId, setVideoByMsgId]     = useState<Record<string, number>>({});
  /** Maps message ID → image job ID for inline diagram cards */
  const [imageByMsgId, setImageByMsgId]     = useState<Record<string, string>>({});
  const [debugData,    setDebugData]         = useState<any>(null);
  const [showNudge,    setShowNudge]         = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const router    = useRouter();
  const { t }        = useTranslation();
  const { language } = useLanguageStore();
  const {
    sessionId, setSessionId, msgCount, user, token, incrementMsg,
    activeConversationId, setActiveConversationId,
    conversations, setConversations, prependConversation,
  } = useSessionStore();

  // Init anonymous session
  useEffect(() => {
    if (!sessionId && !user) {
      createSession().then(s => setSessionId(s.session_id)).catch(() => {});
    }
  }, []);

  // Open conversation from URL params (?conv=<id>&msg=<msgId>)
  // Used when navigating from the Educational Diagrams page.
  // Reads window.location.search directly (avoids useSearchParams + Suspense requirement).
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params    = new URLSearchParams(window.location.search);
    const convParam = params.get('conv');
    const msgParam  = params.get('msg');
    if (!convParam) return;
    handleConversationSelect(convParam).then(() => {
      if (!msgParam) return;
      setTimeout(() => {
        const el = document.querySelector(`[data-msg-id="${msgParam}"]`);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          el.classList.add('ring-2', 'ring-teal-500', 'ring-offset-2', 'rounded-2xl');
          setTimeout(() => el.classList.remove('ring-2', 'ring-teal-500', 'ring-offset-2', 'rounded-2xl'), 2500);
        }
      }, 400);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  // Show profile nudge for logged-in users who haven't set grade/goal yet
  useEffect(() => {
    if (!user?.id) return;
    try { if (localStorage.getItem('profile_nudge_dismissed')) return; } catch {}
    getStudentProfile(user.id, token ?? undefined)
      .then(p => { if (!p.grade || !p.goal) setShowNudge(true); })
      .catch(() => {});
  }, [user?.id]);

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
    setVideoByMsgId({});
    setImageByMsgId({});
    try {
      const [rows, videos, images] = await Promise.all([
        getMessages(id, token ?? undefined),
        getConversationVideos(id, token ?? undefined).catch(() => []),
        listEduImages({ conversation_id: id }, token ?? undefined).catch(() => []),
      ]);

      const loadedMessages = rows.map((m: any) => {
        // asyncpg returns JSONB as raw strings in some configurations —
        // parse defensively so metadata is always a plain object.
        let meta = m.metadata;
        if (typeof meta === 'string') {
          try { meta = JSON.parse(meta); } catch { meta = undefined; }
        }
        // Restore uploaded image URL from persisted metadata
        if (m.role === 'user' && meta?.image_url) {
          meta = { ...meta, imageUrl: meta.image_url };
        }
        return {
          id:       m.id,
          role:     m.role as 'user' | 'assistant',
          content:  m.content,
          metadata: meta ?? undefined,
        };
      });
      setMessages(loadedMessages);

      // Restore inline video cards — two sources merged:
      // 1. DB: getConversationVideos (message_id → video id)
      // 2. localStorage: written at video-creation time, survives refresh
      const restored: Record<string, number> = {};

      // Source 1 — DB: prefer message_id, fall back to last AI message
      const lastAiMsg = loadedMessages.slice().reverse().find(m => m.role === 'assistant');
      for (const v of videos) {
        const key = v.message_id ?? (lastAiMsg?.id ?? null);
        if (key) restored[String(key)] = v.id;
      }

      // Source 2 — localStorage (covers missing ::uuid cast era + anonymous users)
      for (const m of loadedMessages) {
        if (m.role !== 'assistant') continue;
        try {
          const stored = localStorage.getItem(`learnai_video_${m.id}`);
          if (stored) {
            const vid = Number(stored);
            if (vid && !restored[m.id]) restored[m.id] = vid;
          }
        } catch {}
      }

      if (Object.keys(restored).length > 0) setVideoByMsgId(restored);

      // Restore inline image cards — DB first, then localStorage fallback
      const restoredImages: Record<string, string> = {};
      for (const img of images) {
        if (img.message_id && img.id) restoredImages[img.message_id] = img.id;
      }
      for (const m of loadedMessages) {
        if (m.role !== 'assistant') continue;
        try {
          const stored = localStorage.getItem(`learnai_image_${m.id}`);
          if (stored && !restoredImages[m.id]) restoredImages[m.id] = stored;
        } catch {}
      }
      if (Object.keys(restoredImages).length > 0) setImageByMsgId(restoredImages);

      const conv = conversations.find(c => c.id === id);
      if (conv?.subject) setCurrentSubject({ subject: conv.subject, subtopic: conv.subtopic });
    } catch { /* silently ignore */ }
  }

  async function handleDebug(text: string) {
    try {
      const data = await debugChatPrompt({
        message:         text || '(empty)',
        conversation_id: conversationId ?? undefined,
        user_id:         user?.id,
        session_id:      sessionId ?? undefined,
        language,
      }, token ?? undefined);
      setDebugData(data);
    } catch (e) { console.error('Debug prompt error', e); }
  }

  async function handleSend(text: string, file?: File) {
    if (!text && !file) return;

    // Hard gate at anonymous limit
    if (!user && msgCount >= 8) {
      setSignupReason('session_limit');
      setShowSignup(true);
      return;
    }

    // Upload image to R2 for a permanent URL (persists in chat history)
    let imageUrl: string | undefined;
    if (file && file.type.startsWith('image/')) {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
      try {
        imageUrl = await uploadRegionImage(dataUrl, user?.id, sessionId ?? undefined, token ?? undefined);
      } catch {
        // Fall back to base64 so the current turn still works even if upload fails
        imageUrl = dataUrl;
      }
    }

    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      metadata: imageUrl ? { imageUrl } : undefined,
    }]);
    setLoading(true);
    incrementMsg();

    try {
      const res = await sendMessage({
        message: text || 'What is in this image?',
        conversation_id: conversationId ?? undefined,
        user_id:   user?.id,
        session_id: sessionId ?? undefined,
        language,
        image_url: imageUrl,
      }, token ?? undefined);

      setConversationId(res.conversation_id);
      setActiveConversationId(res.conversation_id);
      if (res.subject?.subject) setCurrentSubject(res.subject);

      // Prepend newly-created conversation to the shared sidebar list
      if (!conversationId) {
        prependConversation({
          id:         res.conversation_id,
          title:      text.slice(0, 60),
          subject:    res.subject?.subject,
          subtopic:   res.subject?.subtopic,
          updated_at: new Date().toISOString(),
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

  async function handleMakeVisual(content: string, subject?: string, messageId?: string) {
    if (!user && msgCount >= 8) { setSignupReason('session_limit'); setShowSignup(true); return; }
    try {
      const res = await generateVideo({
        prompt:          content,
        conversation_id: conversationId ?? undefined,
        message_id:      messageId,          // ← link video to the AI message in DB
        user_id:         user?.id,
        session_id:      sessionId ?? undefined,
        subject:         subject ?? currentSubject?.subject,
        language,
      }, token ?? undefined);

      if (!res.supported) {
        setMessages(prev => [...prev, { id: Date.now().toString(), role: 'assistant', content: `🎬 ${res.message}` }]);
        return;
      }

      if (messageId && res.video_id) {
        // Show inline status card — no navigation
        setVideoByMsgId(prev => ({ ...prev, [messageId]: res.video_id! }));
        // Persist to localStorage so the card survives page refresh
        try { localStorage.setItem(`learnai_video_${messageId}`, String(res.video_id)); } catch {}
      } else if (res.video_id) {
        // Fallback: no message context, navigate to /videos
        router.push(`/videos?id=${res.video_id}`);
      }
    } catch (e) { console.error(e); }
  }

  async function handleMakeDiagram(content: string, messageId: string) {
    try {
      const res = await generateEduImage({
        concept:         content.slice(0, 400),
        conversation_id: conversationId ?? undefined,
        message_id:      messageId,
        user_id:         user?.id,
        session_id:      sessionId ?? undefined,
      }, token ?? undefined);

      setImageByMsgId(prev => ({ ...prev, [messageId]: res.jobId }));
      try { localStorage.setItem(`learnai_image_${messageId}`, res.jobId); } catch {}
    } catch (e: any) {
      const isLimit = e?.message === 'session_limit_reached' || e?.message === 'Daily image limit reached';
      if (isLimit && !user) {
        setSignupReason('session_limit');
        setShowSignup(true);
      } else if (isLimit && user) {
        setMessages(prev => [...prev, {
          id: Date.now().toString(), role: 'assistant',
          content: '⚠️ **Daily diagram limit reached.** Come back tomorrow or upgrade your plan.',
        }]);
      } else {
        console.error(e);
      }
    }
  }

  async function handleTestYourself(content: string, subject?: string) {
    if (!user && msgCount >= 8) { setSignupReason('session_limit'); setShowSignup(true); return; }

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
        topic:           content.slice(0, 300),
        conversation_id: conversationId ?? undefined,
        user_id:         user?.id,
        session_id:      sessionId ?? undefined,
        subject:         subject ?? currentSubject?.subject,
        language,
      }, token ?? undefined);

      if (!res.questions || res.questions.length === 0) {
        setMessages(prev => prev.map(m => m.id === loadingId ? {
          id: loadingId, role: 'assistant',
          content: '⚠️ Quiz generation returned no questions. Please try again.',
        } : m));
        return;
      }

      // Save to localStorage so the quiz page has a fast path
      localStorage.setItem(`quiz_${res.quiz_id}`, JSON.stringify(res.questions));

      // Replace loading bubble with a persistent quiz card
      const displayTopic = subject ?? currentSubject?.subject ?? content.slice(0, 60);
      setMessages(prev => prev.map(m => m.id === loadingId ? {
        id:       res.message_id ?? loadingId,   // use DB message id when available
        role:     'assistant',
        content:  `Quiz: ${displayTopic}`,
        metadata: {
          quiz_id:       res.quiz_id,
          quiz_topic:    displayTopic,
          num_questions: res.questions.length,
        },
      } : m));
    } catch (e: any) {
      const msg = e?.message;
      const isLimit = msg === 'session_limit_reached' || msg === 'Daily quiz limit reached';
      if (isLimit && !user) {
        setMessages(prev => prev.filter(m => m.id !== loadingId));
        setSignupReason('session_limit');
        setShowSignup(true);
      } else if (isLimit && user) {
        setMessages(prev => prev.map(m => m.id === loadingId ? {
          id: loadingId, role: 'assistant',
          content: `⚠️ **Daily quiz limit reached.** You've used all your quizzes for today. Come back tomorrow or upgrade your plan.`,
        } : m));
      } else {
        setMessages(prev => prev.map(m => m.id === loadingId ? {
          id: loadingId, role: 'assistant',
          content: `⚠️ **Couldn't generate quiz.** ${msg && msg !== 'Request failed' ? msg : 'Please try again in a moment.'}`,
        } : m));
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
        language,
      }, token ?? undefined);

      setConversationId(res.conversation_id);
      if (res.subject?.subject) setCurrentSubject(res.subject);

      // Prepend newly-created conversation to the shared sidebar list (PDF ask)
      if (!conversationId) {
        prependConversation({
          id:         res.conversation_id,
          title:      question.slice(0, 60),
          subject:    res.subject?.subject,
          subtopic:   res.subject?.subtopic,
          updated_at: new Date().toISOString(),
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
        selectedConversationId={conversationId ?? undefined}
        onNewChat={() => { setMessages([]); setConversationId(null); setActiveConversationId(null); }}
        onConversationSelect={handleConversationSelect}
      />

      <main className="flex-1 flex flex-col min-w-0 bg-[var(--bg)]">
        <div className="flex-1 chat-scroll">
          <MobileTopBar />
          <div className="px-4 pb-6 md:py-6">
          <div className="max-w-2xl mx-auto">
            {messages.length === 0 ? (
              <WelcomeScreen user={user} onSend={handleSend} />
            ) : (
              messages.map(msg => (
                <div key={msg.id} data-msg-id={msg.id} className="transition-all duration-700">
                  <MessageBubble message={msg}
                    onChipClick={handleSend}
                    onMakeVisual={(content, subject) => handleMakeVisual(content, subject, msg.id)}
                    onMakeDiagram={(content, id) => handleMakeDiagram(content, id)}
                    onTestYourself={handleTestYourself}
                    onSimplify={() => handleSend('Can you simplify that explanation?')}
                    onGoDeeper={() => handleSend('Can you go deeper on that?')}
                    videoId={videoByMsgId[msg.id]}
                    imageJobId={imageByMsgId[msg.id]}
                    onDeleteImage={() => setImageByMsgId(prev => { const n = { ...prev }; delete n[msg.id]; return n; })}
                    onDeleteVideo={() => setVideoByMsgId(prev => { const n = { ...prev }; delete n[msg.id]; return n; })}
                    token={token ?? undefined}
                  />
                </div>
              ))
            )}

            {loading && <ThinkingIndicator />}
            <div ref={bottomRef} />
          </div>
          </div>
        </div>

        {/* Credit warning */}
        {!user && msgCount >= 6 && (
          <div className="text-center py-2 text-xs text-[var(--amber)] bg-amber-500/5 border-t border-amber-500/10">
            {t.credits.messagesLeft.replace('{n}', String(8 - msgCount))}
            {' · '}
            <button onClick={() => setShowSignup(true)} className="underline">
              {t.credits.upgradeToKeepLearning}
            </button>
          </div>
        )}

        {showNudge && user && (
          <ProfileNudgeCard
            userId={user.id}
            token={token ?? undefined}
            onComplete={() => { setShowNudge(false); try { localStorage.setItem('profile_nudge_dismissed', '1'); } catch {} }}
            onDismiss={() => { setShowNudge(false); try { localStorage.setItem('profile_nudge_dismissed', '1'); } catch {} }}
          />
        )}
        <InputBar onSend={handleSend} onPdfOpen={f => setPdfFile(f)} loading={loading} onDebug={handleDebug} />
      </main>

      {pdfFile && (
        <PDFViewerModal
          file={pdfFile}
          onClose={() => setPdfFile(null)}
          onAsk={handlePdfAsk}
        />
      )}

      {debugData && <DebugPromptModal data={debugData} onClose={() => setDebugData(null)} />}

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
