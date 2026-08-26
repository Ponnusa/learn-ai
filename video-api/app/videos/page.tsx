"use client";
import { Suspense, useEffect, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { useSessionStore } from "@/lib/sessionStore";
import { listMyVideos, VideoRecord } from "@/lib/api";
import { StatusPill } from "@/components/StatusPill";
import { RequireAuth } from "@/components/RequireAuth";

const IN_PROGRESS = new Set(["pending", "transcript_ready", "queued", "rendering"]);

function VideosInner() {
  const { token } = useSessionStore();
  const highlight = useSearchParams().get("highlight");
  const [videos, setVideos] = useState<VideoRecord[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!token) return;
    const v = await listMyVideos(token);
    setVideos(v);
    setLoading(false);
  }, [token]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  // Poll while anything is still in progress
  useEffect(() => {
    const anyInProgress = videos.some((v) => IN_PROGRESS.has(v.status));
    if (!anyInProgress) return;
    const id = setInterval(load, 8000);
    return () => clearInterval(id);
  }, [videos, load]);

  if (loading) {
    return <div className="max-w-3xl mx-auto px-6 py-16" style={{ color: "var(--text-soft)" }}>Loading…</div>;
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      <h1 className="text-2xl font-semibold mb-8">Videos</h1>

      {videos.length === 0 ? (
        <p style={{ color: "var(--text-soft)" }}>No videos yet.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {videos.map((v) => (
            <div
              key={v.id}
              className="rounded-xl border p-5"
              style={{
                borderColor: String(v.id) === highlight ? "var(--accent)" : "var(--border)",
                background: "var(--surface)",
              }}
            >
              <div className="flex items-start justify-between gap-4 mb-2">
                <p className="font-medium">{v.prompt}</p>
                <StatusPill status={v.status} />
              </div>
              <p className="text-xs mb-3" style={{ color: "var(--text-faint)" }}>
                {v.subject || "auto-detected"} · {v.language} ·{" "}
                {new Date(v.created_at).toLocaleString()}
              </p>

              {v.status === "completed" || v.status === "complete" ? (
                <div className="flex items-center gap-3">
                  {v.video_url && (
                    <a
                      href={v.video_url}
                      download
                      className="text-sm rounded-lg px-3 py-1.5 font-medium"
                      style={{ background: "var(--accent)", color: "#04201C" }}
                    >
                      Download
                    </a>
                  )}
                  {v.video_url && (
                    <a href={v.video_url} target="_blank" rel="noreferrer" className="text-sm underline" style={{ color: "var(--accent-ink)" }}>
                      Watch
                    </a>
                  )}
                </div>
              ) : v.status === "failed" ? (
                <p className="text-sm" style={{ color: "var(--revoked)" }}>{v.error_message || "Generation failed."}</p>
              ) : (
                <p className="text-sm" style={{ color: "var(--text-soft)" }}>Still working — this page refreshes automatically.</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function VideosPage() {
  return (
    <RequireAuth>
      <Suspense fallback={null}>
        <VideosInner />
      </Suspense>
    </RequireAuth>
  );
}
