"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useSessionStore } from "@/lib/sessionStore";
import { getMyApiKey, requestApiKey, listMyVideos, ApiKeyStatus, ApiKeyCreated, VideoRecord, ApiError } from "@/lib/api";
import { StatusPill } from "@/components/StatusPill";
import { RequireAuth } from "@/components/RequireAuth";

function DashboardInner() {
  const { token } = useSessionStore();
  const [key, setKey] = useState<ApiKeyStatus | null>(null);
  const [videos, setVideos] = useState<VideoRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [companyName, setCompanyName] = useState("");
  const [description, setDescription] = useState("");
  const [requesting, setRequesting] = useState(false);
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!token) return;
    const [k, v] = await Promise.all([getMyApiKey(token), listMyVideos(token)]);
    setKey(k);
    setVideos(v);
    setLoading(false);
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleRequest(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setError(null);
    setRequesting(true);
    try {
      const res = await requestApiKey(companyName, description, token);
      setCreated(res);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not request a key — try again.");
    } finally {
      setRequesting(false);
    }
  }

  if (loading) {
    return <div className="max-w-3xl mx-auto px-6 py-16" style={{ color: "var(--text-soft)" }}>Loading…</div>;
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-12 flex flex-col gap-8">
      <h1 className="text-2xl font-semibold">Dashboard</h1>

      {/* API key card */}
      <section className="rounded-xl border p-6" style={{ borderColor: "var(--border)", background: "var(--surface)" }}>
        <h2 className="font-medium mb-4">API key</h2>

        {created && (
          <div className="mb-4 rounded-lg border p-4 text-sm" style={{ borderColor: "var(--accent)", background: "var(--accent-soft)" }}>
            <p className="mb-2 font-medium">Save this key now — it won&apos;t be shown again:</p>
            <code className="block break-all text-xs p-2 rounded" style={{ background: "var(--surface-soft)" }}>
              {created.api_key}
            </code>
          </div>
        )}

        {!key?.has_key ? (
          <form onSubmit={handleRequest} className="flex flex-col gap-3">
            <p className="text-sm" style={{ color: "var(--text-soft)" }}>
              No active key on this account — request one below. A superadmin reviews every request before it&apos;s usable.
            </p>
            <input
              required
              placeholder="Company name"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              className="rounded-lg border px-3 py-2.5 text-sm outline-none"
              style={{ borderColor: "var(--border)", background: "var(--surface-soft)", color: "var(--text)" }}
            />
            <textarea
              required
              placeholder="What are you building?"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="rounded-lg border px-3 py-2.5 text-sm outline-none resize-none"
              style={{ borderColor: "var(--border)", background: "var(--surface-soft)", color: "var(--text)" }}
            />
            {error && <p className="text-sm" style={{ color: "var(--revoked)" }}>{error}</p>}
            <button
              type="submit"
              disabled={requesting}
              className="self-start rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-60"
              style={{ background: "var(--accent)", color: "#04201C" }}
            >
              {requesting ? "Requesting…" : "Request API key"}
            </button>
          </form>
        ) : (
          <div className="flex items-center justify-between">
            <div>
              <StatusPill status={key.status!} />
              <p className="text-sm mt-2" style={{ color: "var(--text-faint)" }}>
                {key.company_name}
              </p>
            </div>
            {key.status === "pending" && (
              <p className="text-sm" style={{ color: "var(--text-soft)" }}>Awaiting review</p>
            )}
          </div>
        )}
      </section>

      {/* Videos card */}
      <section className="rounded-xl border p-6" style={{ borderColor: "var(--border)", background: "var(--surface)" }}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-medium">Videos</h2>
          <Link href="/videos" className="text-sm underline" style={{ color: "var(--accent-ink)" }}>
            View all →
          </Link>
        </div>
        {videos.length === 0 ? (
          <div className="flex items-center justify-between">
            <p className="text-sm" style={{ color: "var(--text-soft)" }}>No videos generated yet.</p>
            {key?.status === "approved" && (
              <Link
                href="/generate"
                className="rounded-lg px-4 py-2 text-sm font-medium"
                style={{ background: "var(--accent)", color: "#04201C" }}
              >
                Generate a video
              </Link>
            )}
          </div>
        ) : (
          <ul className="flex flex-col gap-2">
            {videos.slice(0, 3).map((v) => (
              <li key={v.id} className="flex items-center justify-between text-sm">
                <span className="truncate max-w-[70%]">{v.prompt}</span>
                <StatusPill status={v.status} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardInner />
    </RequireAuth>
  );
}
