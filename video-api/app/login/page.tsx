"use client";
import { useState } from "react";
import { sendMagicLink, ApiError } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [devUrl, setDevUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await sendMagicLink(email);
      setSent(true);
      setDevUrl(res.dev_url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong — try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-sm mx-auto px-6 py-24">
      <h1 className="text-2xl font-semibold mb-2">Sign in</h1>
      <p className="text-sm mb-8" style={{ color: "var(--text-soft)" }}>
        Enter your email — we&apos;ll send a sign-in link, no password needed.
      </p>

      {sent ? (
        <div
          className="rounded-lg border p-4 text-sm"
          style={{ borderColor: "var(--border)", background: "var(--surface)" }}
        >
          <p className="mb-1">Check your inbox — we sent a link to</p>
          <p className="font-mono mb-3">{email}</p>
          {devUrl && (
            <a href={devUrl} className="underline text-xs" style={{ color: "var(--accent-ink)" }}>
              (dev only) open the link directly →
            </a>
          )}
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <input
            type="email"
            required
            placeholder="you@company.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded-lg border px-3 py-2.5 text-sm outline-none"
            style={{ borderColor: "var(--border)", background: "var(--surface)", color: "var(--text)" }}
          />
          {error && (
            <p className="text-sm" style={{ color: "var(--revoked)" }}>
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg px-4 py-2.5 text-sm font-medium disabled:opacity-60"
            style={{ background: "var(--accent)", color: "#04201C" }}
          >
            {loading ? "Sending…" : "Send sign-in link"}
          </button>
        </form>
      )}
    </div>
  );
}
