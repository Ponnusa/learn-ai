"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useSessionStore } from "@/lib/sessionStore";
import { generateVideo, ApiError } from "@/lib/api";
import { RequireAuth } from "@/components/RequireAuth";

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "fi", label: "Finnish" },
  { code: "sv", label: "Swedish" },
  { code: "es", label: "Spanish" },
  { code: "fr", label: "French" },
  { code: "no", label: "Norwegian" },
];

const SUBJECTS = [
  { code: "physics", label: "Physics" },
  { code: "chemistry", label: "Chemistry" },
  { code: "mathematics", label: "Mathematics" },
];

// Fixed for now — other ratios aren't confirmed to render correctly yet.
const ASPECT_RATIO = "16:9";

function GenerateInner() {
  const { token } = useSessionStore();
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [subject, setSubject] = useState(SUBJECTS[0].code);
  const [language, setLanguage] = useState("en");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setError(null);
    setLoading(true);
    try {
      const res = await generateVideo({ topic, subject, language, aspect_ratio: ASPECT_RATIO }, token);
      router.push(`/videos?highlight=${res.video_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start generation — try again.");
      setLoading(false);
    }
  }

  return (
    <div className="max-w-xl mx-auto px-6 py-12">
      <h1 className="text-2xl font-semibold mb-2">Generate a video</h1>
      <p className="text-sm mb-8" style={{ color: "var(--text-soft)" }}>
        One request, one video — accounts are capped at one lifetime generation during the beta.
      </p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <label className="text-sm font-medium block mb-1.5">Topic</label>
          <textarea
            required
            rows={3}
            placeholder="e.g. Newton's laws of motion, explained with a soccer ball"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            className="w-full rounded-lg border px-3 py-2.5 text-sm outline-none resize-none"
            style={{ borderColor: "var(--border)", background: "var(--surface)", color: "var(--text)" }}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium block mb-1.5">Subject</label>
            <select
              required
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full rounded-lg border px-3 py-2.5 text-sm outline-none"
              style={{ borderColor: "var(--border)", background: "var(--surface)", color: "var(--text)" }}
            >
              {SUBJECTS.map((s) => (
                <option key={s.code} value={s.code}>{s.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-sm font-medium block mb-1.5">Language</label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full rounded-lg border px-3 py-2.5 text-sm outline-none"
              style={{ borderColor: "var(--border)", background: "var(--surface)", color: "var(--text)" }}
            >
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>{l.label}</option>
              ))}
            </select>
          </div>
        </div>

        <p className="text-xs" style={{ color: "var(--text-faint)" }}>
          Aspect ratio is fixed at 16:9 for now — other ratios aren&apos;t confirmed to work yet.
        </p>

        {error && <p className="text-sm" style={{ color: "var(--revoked)" }}>{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="self-start rounded-lg px-5 py-2.5 text-sm font-medium disabled:opacity-60"
          style={{ background: "var(--accent)", color: "#04201C" }}
        >
          {loading ? "Starting…" : "Generate"}
        </button>
      </form>
    </div>
  );
}

export default function GeneratePage() {
  return (
    <RequireAuth>
      <GenerateInner />
    </RequireAuth>
  );
}
