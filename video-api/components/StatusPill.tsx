const STYLES: Record<string, { bg: string; color: string }> = {
  pending: { bg: "var(--pending-bg)", color: "var(--pending)" },
  approved: { bg: "var(--approved-bg)", color: "var(--approved)" },
  revoked: { bg: "var(--revoked-bg)", color: "var(--revoked)" },
  completed: { bg: "var(--approved-bg)", color: "var(--approved)" },
  complete: { bg: "var(--approved-bg)", color: "var(--approved)" },
  failed: { bg: "var(--revoked-bg)", color: "var(--revoked)" },
  rendering: { bg: "var(--pending-bg)", color: "var(--pending)" },
  queued: { bg: "var(--pending-bg)", color: "var(--pending)" },
  transcript_ready: { bg: "var(--pending-bg)", color: "var(--pending)" },
};

export function StatusPill({ status }: { status: string }) {
  const style = STYLES[status] || { bg: "var(--surface-soft)", color: "var(--text-soft)" };
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium font-mono"
      style={{ background: style.bg, color: style.color }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: style.color }} />
      {status}
    </span>
  );
}
