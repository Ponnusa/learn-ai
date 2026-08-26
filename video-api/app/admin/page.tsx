"use client";
import { useEffect, useState, useCallback } from "react";
import { useSessionStore } from "@/lib/sessionStore";
import { listDeveloperKeys, approveDeveloperKey, revokeDeveloperKey, setDeveloperKeyTier, DeveloperKeyAdminRow, DeveloperTier, ApiError } from "@/lib/api";

const TIER_OPTIONS: { value: DeveloperTier; label: string }[] = [
  { value: "api_free", label: "Free (2/day, 60s)" },
  { value: "api_standard", label: "Standard (10/day, 120s)" },
  { value: "api_enterprise", label: "Enterprise (unlimited, 180s)" },
];
import { StatusPill } from "@/components/StatusPill";
import { RequireAuth } from "@/components/RequireAuth";

function AdminInner() {
  const { token } = useSessionStore();
  const [keys, setKeys] = useState<DeveloperKeyAdminRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    const rows = await listDeveloperKeys(token);
    setKeys(rows);
    setLoading(false);
  }, [token]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  async function act(fn: (id: string, token: string) => Promise<unknown>, id: string) {
    if (!token) return;
    setError(null);
    setBusyId(id);
    try {
      await fn(id, token);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Action failed — try again.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleTierChange(id: string, tier: DeveloperTier) {
    if (!token) return;
    setError(null);
    setBusyId(id);
    try {
      await setDeveloperKeyTier(id, tier, token);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not change tier — try again.");
    } finally {
      setBusyId(null);
    }
  }

  if (loading) {
    return <div className="max-w-4xl mx-auto px-6 py-16" style={{ color: "var(--text-soft)" }}>Loading…</div>;
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      <h1 className="text-2xl font-semibold mb-8">Developer key requests</h1>

      {error && <p className="text-sm mb-4" style={{ color: "var(--revoked)" }}>{error}</p>}

      {keys.length === 0 ? (
        <p style={{ color: "var(--text-soft)" }}>No requests yet.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {keys.map((k) => (
            <div
              key={k.id}
              className="rounded-xl border p-5 flex items-start justify-between gap-4"
              style={{ borderColor: "var(--border)", background: "var(--surface)" }}
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="font-medium">{k.company_name || k.name || k.email}</span>
                  <StatusPill status={k.status} />
                </div>
                <p className="text-xs mb-2" style={{ color: "var(--text-faint)" }}>
                  {k.email} · requested {new Date(k.created_at).toLocaleDateString()} · {k.videos_generated} video(s) generated
                </p>
                <p className="text-sm" style={{ color: "var(--text-soft)" }}>{k.description}</p>
              </div>
              <div className="flex flex-col items-end gap-2 shrink-0">
                <select
                  value={k.tier}
                  disabled={busyId === k.id}
                  onChange={(e) => handleTierChange(k.id, e.target.value as DeveloperTier)}
                  className="text-xs rounded-lg border px-2 py-1.5 outline-none disabled:opacity-60"
                  style={{ borderColor: "var(--border)", background: "var(--surface-soft)", color: "var(--text)" }}
                >
                  {TIER_OPTIONS.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
                <div className="flex gap-2">
                  {k.status !== "approved" && (
                    <button
                      disabled={busyId === k.id}
                      onClick={() => act(approveDeveloperKey, k.id)}
                      className="text-sm rounded-lg px-3 py-1.5 font-medium disabled:opacity-60"
                      style={{ background: "var(--approved-bg)", color: "var(--approved)" }}
                    >
                      Approve
                    </button>
                  )}
                  {k.status !== "revoked" && (
                    <button
                      disabled={busyId === k.id}
                      onClick={() => act(revokeDeveloperKey, k.id)}
                      className="text-sm rounded-lg px-3 py-1.5 font-medium disabled:opacity-60"
                      style={{ background: "var(--revoked-bg)", color: "var(--revoked)" }}
                    >
                      Revoke
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AdminPage() {
  return (
    <RequireAuth adminOnly>
      <AdminInner />
    </RequireAuth>
  );
}
