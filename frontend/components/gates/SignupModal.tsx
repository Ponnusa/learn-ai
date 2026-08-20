'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { X, Mail, Loader } from 'lucide-react';
import { useTranslation } from '@/hooks/useTranslation';
import { sendMagicLink } from '@/lib/api';
import { useSessionStore } from '@/store/sessionStore';

interface Props {
  reason?: 'session_limit' | 'daily_limit' | 'soft_nudge' | 'video_gate' | 'feature_gate';
  onClose?: () => void;
  savedItems?: string[];
}

export function SignupModal({ reason = 'soft_nudge', onClose, savedItems = [] }: Props) {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { t } = useTranslation();
  const { sessionId } = useSessionStore();
  const router = useRouter();

  const isDismissible = reason === 'soft_nudge' || reason === 'feature_gate';

  async function handleSend() {
    if (!email.trim()) return;
    setLoading(true);
    setError('');
    try {
      await sendMagicLink(email.trim(), sessionId ?? undefined);
      setSent(true);
    } catch (e: any) {
      setError(e.message || t.errors.generic);
    } finally {
      setLoading(false);
    }
  }

  const headlines: Record<string, string> = {
    session_limit: "You've explored your free session!",
    daily_limit:   "You've hit today's limit",
    soft_nudge:    "Don't lose this conversation",
    video_gate:    "Create a free account to generate videos",
    feature_gate:  t.loginGate.title,
  };

  const subtitles: Record<string, string> = {
    session_limit: "Sign up free to keep learning — no credit card needed.",
    daily_limit:   "Come back tomorrow, or sign up for more daily credits.",
    soft_nudge:    "Save your progress with a free account.",
    video_gate:    "Video generation is free — just needs an account.",
    feature_gate:  t.loginGate.body,
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl w-full max-w-md shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between p-6 pb-0">
          <div>
            <h2 className="text-[var(--tx1)] font-bold text-lg">{headlines[reason]}</h2>
            <p className="text-[var(--tx5)] text-sm mt-1">{subtitles[reason]}</p>
          </div>
          {isDismissible && onClose && (
            <button onClick={onClose} className="text-[var(--tx8)] hover:text-[var(--tx1)] ml-4 mt-0.5">
              <X size={18} />
            </button>
          )}
        </div>

        {/* Saved items */}
        {savedItems.length > 0 && (
          <div className="mx-6 mt-4 bg-[var(--ov1)] rounded-xl p-4 space-y-1.5">
            <p className="text-[var(--tx6)] text-xs uppercase tracking-widest mb-2">{t.credits.whatYouGet}</p>
            {savedItems.map((item, i) => (
              <div key={i} className="flex items-center gap-2 text-sm text-[var(--tx3)]">
                <span className="text-[var(--green)]">✓</span>
                <span>{item}</span>
              </div>
            ))}
          </div>
        )}

        {/* Form */}
        <div className="p-6 space-y-3">
          {!sent ? (
            <>
              <div className="flex gap-2">
                <div className="flex-1 flex items-center gap-2 bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-4 py-3">
                  <Mail size={16} className="text-[var(--tx8)] shrink-0" />
                  <input
                    type="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleSend()}
                    placeholder={t.auth.emailPlaceholder}
                    className="bg-transparent text-[var(--tx1)] t-ph outline-none text-sm flex-1"
                  />
                </div>
                <button
                  onClick={handleSend}
                  disabled={loading || !email.trim()}
                  className="px-4 py-3 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-xl transition-colors flex items-center gap-2"
                >
                  {loading ? <Loader size={14} className="animate-spin" /> : null}
                  {t.auth.sendMagicLink}
                </button>
              </div>

              {error && <p className="text-[var(--red)] text-xs">{error}</p>}

              <div className="flex items-center gap-3">
                <div className="flex-1 h-px bg-[var(--bd)]" />
                <span className="text-[var(--tx8)] text-xs">{t.auth.orContinueWith}</span>
                <div className="flex-1 h-px bg-[var(--bd)]" />
              </div>

              <button className="w-full flex items-center justify-center gap-3 bg-[var(--ov1)] hover:bg-[var(--ov3)] border border-[var(--bd)] rounded-xl px-4 py-3 text-[var(--tx3)] text-sm transition-colors">
                <svg width="16" height="16" viewBox="0 0 48 48">
                  <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
                  <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
                  <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
                  <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.36-8.16 2.36-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
                </svg>
                {t.auth.continueWithGoogle}
              </button>

              <p className="text-center text-[var(--tx8)] text-xs">
                Already have an account?{' '}
                <button
                  onClick={() => router.push('/auth/login')}
                  className="text-[var(--purple)] hover:underline"
                >
                  Sign in
                </button>
              </p>
            </>
          ) : (
            <div className="text-center py-4">
              <div className="text-4xl mb-3">📬</div>
              <p className="text-[var(--tx1)] font-medium">{t.auth.magicLinkSent}</p>
              <p className="text-[var(--tx5)] text-sm mt-1">{t.auth.checkEmail}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
