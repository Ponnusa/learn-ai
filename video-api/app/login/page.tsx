"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { login, ApiError } from "@/lib/api";
import { useSessionStore } from "@/lib/sessionStore";

export default function LoginPage() {
  const router = useRouter();
  const setSession = useSessionStore((s) => s.setSession);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await login(email, password);
      setSession(res.token, res.user);
      router.push("/dashboard");
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
        Don&apos;t have an account?{" "}
        <Link href="/signup" className="underline" style={{ color: "var(--accent-ink)" }}>
          Sign up
        </Link>
      </p>

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
        <input
          type="password"
          required
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
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
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
