"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { signup, ApiError } from "@/lib/api";
import { useSessionStore } from "@/lib/sessionStore";

export default function SignupPage() {
  const router = useRouter();
  const setSession = useSessionStore((s) => s.setSession);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await signup(email, password, companyName, description);
      setSession(res.token, res.user);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong — try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-md mx-auto px-6 py-16">
      <h1 className="text-2xl font-semibold mb-2">Request access</h1>
      <p className="text-sm mb-8" style={{ color: "var(--text-soft)" }}>
        Already have an account?{" "}
        <Link href="/login" className="underline" style={{ color: "var(--accent-ink)" }}>
          Sign in
        </Link>
      </p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <div>
          <label className="text-sm font-medium block mb-1.5">Email</label>
          <input
            type="email"
            required
            placeholder="you@company.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border px-3 py-2.5 text-sm outline-none"
            style={{ borderColor: "var(--border)", background: "var(--surface)", color: "var(--text)" }}
          />
        </div>

        <div>
          <label className="text-sm font-medium block mb-1.5">Password</label>
          <input
            type="password"
            required
            minLength={8}
            placeholder="At least 8 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border px-3 py-2.5 text-sm outline-none"
            style={{ borderColor: "var(--border)", background: "var(--surface)", color: "var(--text)" }}
          />
        </div>

        <div>
          <label className="text-sm font-medium block mb-1.5">Company name</label>
          <input
            required
            placeholder="e.g. Acme Learning"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            className="w-full rounded-lg border px-3 py-2.5 text-sm outline-none"
            style={{ borderColor: "var(--border)", background: "var(--surface)", color: "var(--text)" }}
          />
        </div>

        <div>
          <label className="text-sm font-medium block mb-1.5">What are you building?</label>
          <textarea
            required
            rows={3}
            placeholder="A short description of your product and how you'd use the API…"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full rounded-lg border px-3 py-2.5 text-sm outline-none resize-none"
            style={{ borderColor: "var(--border)", background: "var(--surface)", color: "var(--text)" }}
          />
        </div>

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
          {loading ? "Creating account…" : "Create account & request a key"}
        </button>

        <p className="text-xs" style={{ color: "var(--text-faint)" }}>
          A superadmin reviews every request before your key becomes usable.
        </p>
      </form>
    </div>
  );
}
