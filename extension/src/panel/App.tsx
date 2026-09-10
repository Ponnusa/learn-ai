import { useEffect, useRef, useState } from 'react';
import { Crosshair } from 'lucide-react';
import {
  createOrGetSession,
  generateQuiz,
  sendMessage,
  updateLanguage,
  uploadRegionImage,
  LANGUAGE_CODES,
  LANGUAGE_LABELS,
  type AuthResponse,
  type AuthUser,
  type LanguageCode,
  type QuizQuestion,
} from '../lib/api';
import { LadderWidget } from '../components/LadderWidget';
import { EurekaBurst, EUREKA_BURST_DURATION } from '../components/EurekaBurst';
import { GenieMessage, type GenieMessageData } from './GenieMessage';
import { GenieQuiz } from './GenieQuiz';
import { GenieAuth } from './GenieAuth';
import { ClipCapture } from './ClipCapture';
import { GENIE_TRANSLATIONS } from '../lib/i18n';

const SESSION_STORAGE_KEY = 'genie_session_id';
const AUTH_TOKEN_KEY = 'genie_auth_token';
const AUTH_USER_KEY = 'genie_auth_user';
const LANGUAGE_STORAGE_KEY = 'genie_language';

/** Best guess at a starting language before any saved preference loads:
 *  the browser's own locale, mapped to the nearest of the 6 supported
 *  codes, falling back to English. */
function detectDefaultLanguage(): LanguageCode {
  const nav = (navigator.language || 'en').slice(0, 2).toLowerCase();
  return (LANGUAGE_CODES as string[]).includes(nav) ? (nav as LanguageCode) : 'en';
}

interface PendingSelection {
  text: string;
  pageTitle: string;
  pageUrl: string;
  action?: 'quiz'; // set by the "Quiz me on this" context-menu entry
}

interface AuthState {
  token: string;
  user: AuthUser;
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
  const bottomRef = useRef<HTMLDivElement>(null);

  const [auth, setAuth] = useState<AuthState | null>(null);
  const [showAuth, setShowAuth] = useState(false);

  // Response language — mirrors frontend/hooks/useLanguage.ts's behavior:
  // starts from a locally-remembered choice (or the browser locale),
  // snaps to the signed-in account's saved `language` on sign-in/restore
  // (same PATCH /api/auth/language persists a manual change back), and is
  // sent on every request that affects the AI's output (previously wasn't
  // sent at all, so genie silently always talked in English).
  const [language, setLanguageState] = useState<LanguageCode>(detectDefaultLanguage());
  const t = GENIE_TRANSLATIONS[language];

  // Screen-clip attachment: `clipping` holds the full captured tab while
  // the crop UI is open; `clippedImage` holds the confirmed crop staged
  // for the next message (uploaded lazily at send time, not on capture).
  const [clipping, setClipping] = useState<string | null>(null);
  const [clippedImage, setClippedImage] = useState<string | null>(null);
  const [clipUploading, setClipUploading] = useState(false);

  const [quiz, setQuiz] = useState<{ quizId: string; questions: QuizQuestion[] } | null>(null);
  const [quizGenerating, setQuizGenerating] = useState(false);
  const [quizError, setQuizError] = useState<string | null>(null);
  const [quizLimitReached, setQuizLimitReached] = useState(false);
  // How many messages existed when the quiz was requested — lets the quiz
  // render in its actual chronological spot in the message list (it used
  // to be a fixed element between the scroll area and the input box, so it
  // stayed visually pinned at the bottom forever instead of scrolling away
  // with the rest of the conversation like everything else does).
  const [quizAnchorIndex, setQuizAnchorIndex] = useState<number | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, loading, selection, quiz, quizGenerating]);

  // Same climbing/eureka state machine as frontend/app/page.tsx's
  // updateLadderState — see that file's comments for why steps are
  // tracked via a ref (sync, not stale inside the async send handler)
  // alongside mirrored state (to trigger re-renders).
  const ladderRef = useRef({ active: false, steps: 0 });
  const [ladderPhase, setLadderPhase] = useState<'idle' | 'climbing' | 'eureka'>('idle');
  const [ladderSteps, setLadderSteps] = useState(0);
  const [eurekaBurst, setEurekaBurst] = useState(false);

  // ── Bootstrap: session, saved sign-in, and any selection that triggered
  //    opening the panel (pill, or the right-click context menu) ───────────
  useEffect(() => {
    chrome.storage.local.get(SESSION_STORAGE_KEY).then(async (stored) => {
      try {
        const res = await createOrGetSession(stored[SESSION_STORAGE_KEY] ?? null);
        setSessionId(res.session_id);
        await chrome.storage.local.set({ [SESSION_STORAGE_KEY]: res.session_id });
      } catch {
        setError(t.connectionError);
      }
    });

    chrome.storage.local.get([AUTH_TOKEN_KEY, AUTH_USER_KEY, LANGUAGE_STORAGE_KEY]).then((stored) => {
      const savedLanguage: LanguageCode | undefined = stored[LANGUAGE_STORAGE_KEY];
      if (stored[AUTH_TOKEN_KEY] && stored[AUTH_USER_KEY]) {
        const user: AuthUser = stored[AUTH_USER_KEY];
        setAuth({ token: stored[AUTH_TOKEN_KEY], user });
        // Account's saved language wins over a locally-remembered one on
        // restore — same precedence frontend/hooks/useLanguage.ts uses.
        const accountLanguage = user.language as LanguageCode | undefined;
        if (accountLanguage && LANGUAGE_CODES.includes(accountLanguage)) {
          setLanguageState(accountLanguage);
          return;
        }
      }
      if (savedLanguage && LANGUAGE_CODES.includes(savedLanguage)) setLanguageState(savedLanguage);
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

  // A selection that arrived with action:'quiz' (right-click "Quiz me on
  // this") already expressed clear intent — auto-run the quiz instead of
  // waiting for a button click. Split into its own effect (rather than
  // calling handleQuiz directly from the mount-only bootstrap effect above)
  // so it always closes over the current sessionId/auth, not whatever they
  // were at the first render before the session finished loading.
  useEffect(() => {
    if (selection?.action === 'quiz' && sessionId) {
      const text = selection.text;
      setSelection(null);
      handleQuiz(text);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection, sessionId]);

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
    const hasImage = !!clippedImage;
    if ((!text.trim() && !hasImage) || loading || limitReached || !sessionId) return;
    setError(null);
    setInput('');
    setSelection(null);
    const pendingClip = clippedImage;
    setClippedImage(null);

    // Deliberately English regardless of `language`, matching
    // frontend/app/page.tsx's handlePdfAsk default ('What is in this
    // image?') exactly — the web app doesn't localize this one either.
    const messageText = text.trim() || 'What does this show? Please explain.';

    let imageUrl: string | undefined;
    if (pendingClip) {
      setClipUploading(true);
      try {
        imageUrl = await uploadRegionImage(pendingClip, auth?.user.id, auth ? undefined : (sessionId ?? undefined), auth?.token);
      } catch {
        setError(t.uploadError);
        setClipUploading(false);
        return;
      }
      setClipUploading(false);
    }

    const userMsg: GenieMessageData = {
      id: `local-${Date.now()}`,
      role: 'user',
      content: messageText,
      metadata: imageUrl ? { imageUrl } : undefined,
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await sendMessage(
        {
          message: messageText,
          conversation_id: conversationId ?? undefined,
          session_id: auth ? undefined : sessionId,
          user_id: auth?.user.id,
          source: 'extension',
          image_url: imageUrl,
          language,
        },
        auth?.token,
      );
      setConversationId(res.conversation_id);
      updateLadderState(res.ladder_depth);
      setMessages((prev) => [
        ...prev,
        {
          id: res.message_id,
          role: 'assistant',
          content: res.reply,
          metadata: { chips: res.chips, ladder_depth: res.ladder_depth },
        },
      ]);
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

  async function handleClipScreen() {
    setError(null);
    try {
      // No windowId -> captures the current window's active tab. Requires
      // no permission beyond the host_permissions ("<all_urls>") already
      // declared in manifest.json — captureVisibleTab checks the extension
      // has host access to the tab being captured, which that covers.
      const dataUrl = await chrome.tabs.captureVisibleTab({ format: 'png' });
      setClipping(dataUrl);
    } catch {
      setError(t.captureError);
    }
  }

  function handleClipConfirm(cropped: string) {
    setClipping(null);
    setClippedImage(cropped);
  }

  async function handleQuiz(topic: string) {
    if (quizGenerating) return;
    setSelection(null);
    setQuizError(null);
    setQuizGenerating(true);
    setQuizAnchorIndex(messages.length);

    try {
      const res = await generateQuiz(
        {
          topic,
          conversation_id: conversationId ?? undefined,
          session_id: auth ? undefined : (sessionId ?? undefined),
          user_id: auth?.user.id,
          language,
        },
        auth?.token,
      );
      setQuiz({ quizId: res.quiz_id, questions: res.questions });
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Could not generate a quiz';
      if (msg === 'session_limit_reached') {
        setQuizLimitReached(true);
      } else {
        setQuizError(msg);
      }
    } finally {
      setQuizGenerating(false);
    }
  }

  function handleAuthSuccess(res: AuthResponse) {
    setAuth({ token: res.token, user: res.user });
    chrome.storage.local.set({ [AUTH_TOKEN_KEY]: res.token, [AUTH_USER_KEY]: res.user });
    setShowAuth(false);
    // A signed-in user's credit limit is a completely separate check
    // (their own daily allowance, not the anonymous session's lifetime
    // cap) — clear both so the UI reflects the new state immediately.
    setLimitReached(false);
    setQuizLimitReached(false);
    // Snap to the account's saved language, same precedence as the web
    // app's useLanguage() hook on login.
    const accountLanguage = res.user.language as LanguageCode | undefined;
    if (accountLanguage && LANGUAGE_CODES.includes(accountLanguage)) {
      setLanguageState(accountLanguage);
      chrome.storage.local.set({ [LANGUAGE_STORAGE_KEY]: accountLanguage });
    }
  }

  function handleSignOut() {
    setAuth(null);
    chrome.storage.local.remove([AUTH_TOKEN_KEY, AUTH_USER_KEY]);
    // The conversation just signed out of belongs to that account — keeping
    // it visible after sign-out would let the next person to open the
    // panel (a shared machine, say) read someone else's chat history.
    setMessages([]);
    setConversationId(null);
    setQuiz(null);
    setQuizAnchorIndex(null);
    setQuizGenerating(false);
    setQuizError(null);
    setQuizLimitReached(false);
    setSelection(null);
    setError(null);
    setInput('');
    setClipping(null);
    setClippedImage(null);
    setLimitReached(false);
    ladderRef.current = { active: false, steps: 0 };
    setLadderPhase('idle');
    setLadderSteps(0);
    setEurekaBurst(false);
  }

  function handleLanguageChange(lang: LanguageCode) {
    setLanguageState(lang);
    chrome.storage.local.set({ [LANGUAGE_STORAGE_KEY]: lang });
    if (auth) {
      updateLanguage(auth.user.id, lang, auth.token).catch(() => {});
      setAuth({ ...auth, user: { ...auth.user, language: lang } });
    }
  }

  // Per-message action toolbar handlers — mirror frontend/app/page.tsx's
  // onChipClick/onTestYourself/onSimplify/onGoDeeper exactly, including
  // which ones are localized: walkMeThroughPrompt is (t.walkMeThroughPrompt,
  // same as the app's t.chat.walkMeThroughPrompt), but simplify/go-deeper
  // stay hardcoded English on purpose — the app itself hardcodes those two
  // (frontend/app/page.tsx's onSimplify/onGoDeeper) regardless of the
  // user's language, so matching that is matching the app, not a gap.
  const handleChipClick = (chip: string) => handleSend(chip);
  const handleWalkMeThrough = () => handleSend(t.walkMeThroughPrompt);
  const handleQuizMe = (content: string) => handleQuiz(content.slice(0, 300));
  const handleSimplify = () => handleSend('Can you simplify that explanation?');
  const handleGoDeeper = () => handleSend('Can you go deeper on that?');

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center gap-2 px-4 py-3 border-b border-[var(--bd)]">
        <span className="text-lg">🧞</span>
        <span className="font-semibold text-[var(--tx1)] text-sm flex-1">LearnX Genie</span>
        <select
          value={language}
          onChange={(e) => handleLanguageChange(e.target.value as LanguageCode)}
          title="Response language"
          aria-label="Response language"
          className="text-xs bg-transparent text-[var(--tx7)] hover:text-[var(--tx1)] border border-[var(--bd)] rounded-lg px-1.5 py-1 outline-none cursor-pointer"
        >
          {LANGUAGE_CODES.map((code) => (
            <option key={code} value={code}>
              {LANGUAGE_LABELS[code]}
            </option>
          ))}
        </select>
        {auth ? (
          <button
            type="button"
            className="text-xs text-[var(--tx7)] hover:text-[var(--tx1)]"
            onClick={handleSignOut}
            title={auth.user.email}
          >
            {t.signOut}
          </button>
        ) : (
          <button
            type="button"
            className="text-xs font-medium text-[var(--indigo)] hover:underline"
            onClick={() => setShowAuth((v) => !v)}
          >
            {t.signIn}
          </button>
        )}
      </header>

      {showAuth && (
        <GenieAuth
          t={t}
          sessionId={sessionId}
          onSuccess={handleAuthSuccess}
          onCancel={() => setShowAuth(false)}
        />
      )}

      {clipping && (
        <ClipCapture t={t} dataUrl={clipping} onConfirm={handleClipConfirm} onCancel={() => setClipping(null)} />
      )}

      <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-3">
        {messages.length === 0 && !selection && !quiz && !quizGenerating && (
          <p className="text-sm text-[var(--tx7)] leading-relaxed">{t.welcomeHint}</p>
        )}

        {messages.slice(0, quizAnchorIndex ?? messages.length).map((m) => (
          <GenieMessage
            key={m.id}
            message={m}
            language={language}
            t={t}
            onChipClick={handleChipClick}
            onQuizMe={handleQuizMe}
            onWalkMeThrough={handleWalkMeThrough}
            onSimplify={handleSimplify}
            onGoDeeper={handleGoDeeper}
          />
        ))}

        {(quizGenerating || quizError || quizLimitReached || quiz) && (
          <div className="flex flex-col gap-2">
            {quizGenerating && <p className="text-xs text-[var(--tx7)]">{t.buildingQuiz}</p>}
            {quizError && <p className="text-xs text-[var(--red)]">{quizError}</p>}
            {quizLimitReached && !auth && (
              <div className="p-2.5 rounded-xl border border-[var(--bd)] bg-[var(--surface)] text-center">
                <p className="text-xs text-[var(--tx2)]">{t.quizLimitMsg}</p>
                <button
                  type="button"
                  className="text-xs font-medium text-[var(--indigo)] hover:underline mt-1"
                  onClick={() => setShowAuth(true)}
                >
                  {t.signInForMore}
                </button>
              </div>
            )}
            {quiz && (
              <GenieQuiz
                key={quiz.quizId}
                t={t}
                quizId={quiz.quizId}
                questions={quiz.questions}
                userId={auth?.user.id}
                token={auth?.token}
              />
            )}
          </div>
        )}

        {messages.slice(quizAnchorIndex ?? messages.length).map((m) => (
          <GenieMessage
            key={m.id}
            message={m}
            language={language}
            t={t}
            onChipClick={handleChipClick}
            onQuizMe={handleQuizMe}
            onWalkMeThrough={handleWalkMeThrough}
            onSimplify={handleSimplify}
            onGoDeeper={handleGoDeeper}
          />
        ))}

        {loading && <p className="text-xs text-[var(--tx7)]">{t.thinking}</p>}
        {error && <p className="text-xs text-[var(--red)]">{error}</p>}
        <div ref={bottomRef} />
      </div>

      <LadderWidget phase={ladderPhase} steps={ladderSteps} />

      {/* Every conversation genie starts is a real conversation on the
          account/session (see handleSend/handleQuiz) — this link is
          genuinely "continue there," not just a marketing nudge. Deep-links
          to the specific conversation via ?conv=<id>, the exact param
          frontend/app/page.tsx already reads on load (confirmed: 'conv',
          not 'conversation_id'). Note: there's no equivalent session_id
          URL param on the web app side, so for an anonymous (not signed
          in) user this opens the app's OWN separate anonymous session, not
          this one's — true continuity there would need new web-app work,
          not just an extension-side change. */}
      {(messages.length > 0 || quiz) && (
        <a
          href={conversationId ? `https://learnx-ai.com/?conv=${conversationId}` : 'https://learnx-ai.com'}
          target="_blank"
          rel="noopener noreferrer"
          className="block text-center text-[11px] text-[var(--tx7)] hover:text-[var(--indigo)] py-1.5 border-t border-[var(--bd)] transition-colors"
        >
          {t.continueInLearnX}
        </a>
      )}

      {selection && (
        <div className="mx-4 mb-2 p-2.5 rounded-xl border border-[var(--bd)] bg-[var(--surface)]">
          <div className="flex items-start justify-between gap-2 mb-2">
            <p className="text-xs text-[var(--tx7)] line-clamp-2">"{selection.text}"</p>
            <button
              type="button"
              aria-label={t.cancelSelectionTitle}
              title={t.cancelSelectionTitle}
              className="shrink-0 text-[var(--tx7)] hover:text-[var(--tx1)] text-sm leading-none"
              onClick={() => setSelection(null)}
            >
              ✕
            </button>
          </div>
          {/* The first button leads and is visually primary — it's the one
              that nudges the adaptive-teaching prompt toward guided
              discovery (the ladder/eureka experience), which is genie's
              actual differentiator. t.walkMeThroughSelection mirrors the
              in-app "Walk me through it" chip's proven wording
              (walkMeThroughPrompt in frontend/translations/*.ts) as closely
              as possible, adapted to embed the selected text since this is
              the first message (no prior reply for "that" to refer to) — a
              plain "help me understand X" is technically listed as a
              trigger phrase in ADAPTIVE_TEACHING_INSTRUCTIONS too, but in
              practice wasn't a strong enough signal on its own for a broad
              multi-part topic ("Newton's laws of motion") and the model
              just gave a full explanation instead of scaffolding. The
              explicit "one guiding question at a time, instead of just
              explaining it" clause is what actually maps onto that
              instruction's single-question rule. */}
          <div className="flex flex-wrap gap-2">
            <button
              className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-[var(--indigo)] text-white inline-flex items-center gap-1"
              onClick={() => handleSend(t.walkMeThroughSelection(selection.text))}
            >
              {t.walkMeThrough}
            </button>
            <button
              className="text-xs font-medium px-2.5 py-1.5 rounded-lg border border-[var(--bd)] text-[var(--tx3)]"
              onClick={() => handleSend(t.explainThis(selection.text))}
            >
              {t.justExplainIt}
            </button>
            <button
              className="text-xs font-medium px-2.5 py-1.5 rounded-lg border border-[var(--bd)] text-[var(--tx3)]"
              onClick={() => handleQuiz(selection.text)}
            >
              {t.quizMeOnThis}
            </button>
          </div>
        </div>
      )}

      {limitReached ? (
        <div className="m-4 p-3 rounded-xl border border-[var(--bd)] bg-[var(--surface)] text-center">
          <p className="text-sm text-[var(--tx2)]">{t.limitReachedMsg}</p>
          <button
            type="button"
            className="text-xs font-medium text-[var(--indigo)] hover:underline mt-1"
            onClick={() => setShowAuth(true)}
          >
            {t.signInToKeepGoing}
          </button>
        </div>
      ) : (
        <>
          {clippedImage && (
            <div className="flex items-center gap-2 mx-3 mt-2 p-1.5 rounded-lg border border-[var(--bd)] bg-[var(--surface)]">
              <img src={clippedImage} alt="Clipped region" className="w-10 h-10 object-cover rounded" />
              <span className="text-xs text-[var(--tx7)] flex-1">{t.clipAttached}</span>
              <button
                type="button"
                aria-label={t.removeClip}
                className="text-[var(--tx7)] hover:text-[var(--tx1)] text-sm leading-none px-1"
                onClick={() => setClippedImage(null)}
              >
                ✕
              </button>
            </div>
          )}
          <form
            className="flex items-center gap-2 p-3 border-t border-[var(--bd)]"
            onSubmit={(e) => {
              e.preventDefault();
              handleSend(input);
            }}
          >
            <button
              type="button"
              title={t.clipButtonTitle}
              aria-label={t.clipButtonTitle}
              onClick={handleClipScreen}
              disabled={loading || clipUploading}
              className="text-[var(--tx7)] hover:text-[var(--tx1)] p-2 rounded-lg hover:bg-[var(--ov1)] disabled:opacity-50"
            >
              <Crosshair size={16} />
            </button>
            <input
              className="flex-1 rounded-lg border border-[var(--bd)] bg-[var(--input)] text-[var(--tx1)] text-sm px-3 py-2 outline-none"
              placeholder={clippedImage ? t.askAboutThisPlaceholder : t.chatPlaceholder}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
            />
            <button
              type="submit"
              className="text-sm font-medium px-3 py-2 rounded-lg bg-[var(--indigo)] text-white disabled:opacity-50"
              disabled={loading || clipUploading || (!input.trim() && !clippedImage)}
            >
              {clipUploading ? t.uploading : t.send}
            </button>
          </form>
        </>
      )}

      <EurekaBurst active={eurekaBurst} />
    </div>
  );
}
