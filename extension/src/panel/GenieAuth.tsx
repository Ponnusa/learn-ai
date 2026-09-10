import { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { loginPassword, register, type AuthResponse } from '../lib/api';
import type { GenieStrings } from '../lib/i18n';

interface GenieAuthProps {
  t: GenieStrings;
  sessionId: string | null;
  onSuccess: (auth: AuthResponse) => void;
  onCancel: () => void;
}

// Email/password rather than magic-link or Google OAuth: both of those
// redirect through a browser tab to a *web page* (backend/routers/auth.py's
// magic-link only honors VIDEO_API_URL as an alternate redirect target, and
// OAuth needs a full-page redirect flow), so the resulting JWT would land in
// the web app's localStorage, not somewhere the extension can read it —
// there's no code-exchange endpoint today to hand it back to a panel. Email/
// password POSTs return { token, user } directly in the response, so the
// panel gets the token with no cross-origin hop needed at all.
export function GenieAuth({ t, sessionId, onSuccess, onCancel }: GenieAuthProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const auth =
        mode === 'login' ? await loginPassword(email, password) : await register(email, password, sessionId);
      onSuccess(auth);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.authGenericError);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-4 mb-2 p-3 rounded-xl border border-[var(--bd)] bg-[var(--surface)] flex flex-col gap-2.5">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-[var(--tx1)]">
          {mode === 'login' ? t.signInTitle : t.createAccountTitle}
        </span>
        <button
          type="button"
          aria-label="Cancel sign-in"
          className="text-[var(--tx7)] hover:text-[var(--tx1)] text-sm leading-none"
          onClick={onCancel}
        >
          ✕
        </button>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-2">
        <input
          type="email"
          required
          placeholder={t.emailPlaceholder}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="rounded-lg border border-[var(--bd)] bg-[var(--input)] text-[var(--tx1)] text-sm px-3 py-2 outline-none"
        />
        <div className="relative">
          <input
            type={passwordVisible ? 'text' : 'password'}
            required
            minLength={mode === 'register' ? 8 : undefined}
            placeholder={mode === 'register' ? t.passwordMinPlaceholder : t.passwordPlaceholder}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-[var(--bd)] bg-[var(--input)] text-[var(--tx1)] text-sm pl-3 pr-9 py-2 outline-none"
          />
          <button
            type="button"
            tabIndex={-1}
            aria-label={passwordVisible ? t.hidePassword : t.showPassword}
            title={passwordVisible ? t.hidePassword : t.showPassword}
            onClick={() => setPasswordVisible((v) => !v)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--tx7)] hover:text-[var(--tx1)] p-0.5"
          >
            {passwordVisible ? <EyeOff size={15} /> : <Eye size={15} />}
          </button>
        </div>
        {error && <p className="text-xs text-[var(--red)]">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="text-sm font-medium px-3 py-2 rounded-lg bg-[var(--indigo)] text-white disabled:opacity-50"
        >
          {loading ? t.pleaseWait : mode === 'login' ? t.signIn : t.createAccount}
        </button>
      </form>

      <button
        type="button"
        className="text-xs text-[var(--tx7)] hover:text-[var(--tx1)] self-center"
        onClick={() => setMode((m) => (m === 'login' ? 'register' : 'login'))}
      >
        {mode === 'login' ? t.noAccountPrompt : t.hasAccountPrompt}
      </button>
    </div>
  );
}
