'use client';
import { useEffect, useState } from 'react';
import { X, Loader2, Footprints, Lightbulb, TrendingUp, ArrowUpRight, RotateCcw } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface RadarDimension {
  level: string;
  description: string;
  confidence: string;
  observable_evidence: string[];
  support_level: string;
  next_growth_step: string;
}
interface ReportBody {
  academic_understanding: { level: string; summary: string };
  thinking_radar: {
    decision_making: RadarDimension;
    justification: RadarDimension;
    constraint_awareness: RadarDimension;
    transfer: RadarDimension;
  };
  strengths: string[];
  areas_for_growth: string[];
  next_steps: string[];
  teacher_insight: string;
  suggested_next_topic: string;
  optional_extension: string;
}
interface ReportEntry {
  id: string;
  status: 'pending' | 'ready' | 'failed';
  steps: number;
  report: ReportBody | null;
  error_message: string | null;
  created_at: string;
}

const DIMENSION_LABELS: [keyof ReportBody['thinking_radar'], string][] = [
  ['decision_making', 'Decision-Making'],
  ['justification', 'Justification'],
  ['constraint_awareness', 'Constraint Awareness'],
  ['transfer', 'Transfer'],
];

const LEVEL_STYLE: Record<string, string> = {
  'Limited Evidence': 'text-[var(--tx7)] border-[var(--bd)] bg-[var(--ov1)]',
  'Beginner':         'text-red-400 border-red-500/30 bg-red-500/10',
  'Developing':       'text-amber-400 border-amber-500/30 bg-amber-500/10',
  'Proficient':       'text-green-400 border-green-500/30 bg-green-500/10',
  'Advanced':         'text-blue-400 border-blue-500/30 bg-blue-500/10',
};
function levelStyle(level: string): string {
  return LEVEL_STYLE[level] ?? LEVEL_STYLE['Limited Evidence'];
}

export function LevelPill({ level }: { level: string }) {
  return (
    <span className={`text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full border ${levelStyle(level)}`}>
      {level}
    </span>
  );
}

function RadarCard({ label, dim }: { label: string; dim: RadarDimension }) {
  return (
    <div className="bg-[var(--ov1)] border border-[var(--bd)] rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[var(--tx1)] text-sm font-semibold">{label}</span>
        <LevelPill level={dim.level} />
      </div>
      <p className="text-[var(--tx3)] text-xs leading-relaxed mb-3">{dim.description}</p>
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-[10px] mb-2">
        <div><span className="text-[var(--tx8)] uppercase tracking-wide">Confidence</span><p className="text-[var(--tx3)] mt-0.5">{dim.confidence}</p></div>
        <div><span className="text-[var(--tx8)] uppercase tracking-wide">Support level</span><p className="text-[var(--tx3)] mt-0.5">{dim.support_level}</p></div>
      </div>
      {dim.observable_evidence?.length > 0 && (
        <div className="mb-2">
          <span className="text-[10px] text-[var(--tx8)] uppercase tracking-wide">Observable evidence</span>
          <ul className="mt-1 space-y-0.5">
            {dim.observable_evidence.map((e, i) => (
              <li key={i} className="text-[var(--tx4)] text-xs flex items-start gap-1.5">
                <span className="text-[var(--tx8)] shrink-0">•</span>{e}
              </li>
            ))}
          </ul>
        </div>
      )}
      {dim.next_growth_step && (
        <p className="text-[10px] text-purple-300/80 border-t border-[var(--bd)] pt-2 mt-2">
          <span className="text-[var(--tx8)] uppercase tracking-wide">Next: </span>{dim.next_growth_step}
        </p>
      )}
    </div>
  );
}

function BulletList({ items, color }: { items: string[]; color: string }) {
  return (
    <ul className="space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="text-[var(--tx3)] text-xs flex items-start gap-2">
          <span className={`shrink-0 mt-1 w-1.5 h-1.5 rounded-full ${color}`} />
          {item}
        </li>
      ))}
    </ul>
  );
}

export function LadderReportModal({
  conceptId, studentId, conceptTitle, studentName, onClose, fetchUrl, token,
}: {
  conceptId: string;
  studentId: string;
  conceptTitle: string;
  studentName: string;
  onClose: () => void;
  fetchUrl: string;
  token: string | null;
}) {
  const [reports, setReports] = useState<ReportEntry[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [pollKey, setPollKey] = useState(0);
  const [regenerating, setRegenerating] = useState(false);

  // Report generation takes several seconds (a real AI call, run as a
  // background task) — poll while any report is still 'pending' so a
  // teacher who opens this right after a chain resolves sees it flip to
  // 'ready' on its own instead of looking stuck until they close/reopen.
  // pollKey is bumped by regenerate() below to re-enter this same effect
  // and restart polling after manually kicking a report back to pending.
  useEffect(() => {
    let cancelled = false;
    let intervalId: ReturnType<typeof setInterval> | undefined;

    async function load() {
      try {
        const res = await fetch(`${API_BASE}${fetchUrl}`, { headers: { Authorization: `Bearer ${token}` } });
        const d = res.ok ? await res.json() : { reports: [] };
        if (cancelled) return;
        const list: ReportEntry[] = d.reports ?? [];
        setReports(list);
        setSelected(prev => prev ?? list[0]?.id ?? null);

        const stillPending = list.some(r => r.status === 'pending');
        if (stillPending && !intervalId) intervalId = setInterval(load, 3000);
        else if (!stillPending && intervalId) { clearInterval(intervalId); intervalId = undefined; }
      } catch {
        if (!cancelled) setReports(prev => prev ?? []);
      }
    }

    load();
    return () => { cancelled = true; if (intervalId) clearInterval(intervalId); };
  }, [fetchUrl, token, pollKey]);

  const active = reports?.find(r => r.id === selected) ?? null;

  async function regenerate() {
    if (!active || regenerating) return;
    setRegenerating(true);
    try {
      await fetch(`${API_BASE}/api/courses/concepts/${conceptId}/students/${studentId}/ladder-reports/${active.id}/regenerate`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` },
      });
      setPollKey(k => k + 1);
    } finally {
      setRegenerating(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[80] bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl max-w-2xl w-full max-h-[85vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        <div className="sticky top-0 bg-[var(--surface)] border-b border-[var(--bd)] px-5 py-4 flex items-start justify-between gap-3 z-10">
          <div>
            <p className="text-[10px] text-purple-400 uppercase tracking-wider font-semibold flex items-center gap-1.5">
              <Footprints size={11} /> Ladder Session Report
            </p>
            <h2 className="text-[var(--tx1)] text-lg font-bold mt-0.5">{conceptTitle}</h2>
            <p className="text-[var(--tx7)] text-xs mt-0.5">{studentName}</p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            {active && active.status !== 'pending' && (
              <button onClick={regenerate} disabled={regenerating}
                title="Re-run the AI scoring for this session — useful if this report looks off"
                className="flex items-center gap-1.5 text-[10px] px-2.5 py-1.5 rounded-lg border border-[var(--bd)]
                           text-[var(--tx7)] hover:border-purple-500/40 hover:text-purple-400 transition-all disabled:opacity-50">
                {regenerating ? <Loader2 size={12} className="animate-spin" /> : <RotateCcw size={12} />}
                Regenerate
              </button>
            )}
            <button onClick={onClose} className="text-[var(--tx7)] hover:text-[var(--tx2)] transition-colors">
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Session picker — only shown when more than one resolved chain exists */}
        {reports && reports.length > 1 && (
          <div className="px-5 pt-3 flex flex-wrap gap-1.5">
            {reports.map((r, i) => (
              <button key={r.id} onClick={() => setSelected(r.id)}
                className={`text-[10px] px-2.5 py-1 rounded-full border transition-colors ${
                  r.id === selected
                    ? 'border-purple-500/50 bg-purple-500/15 text-purple-300'
                    : 'border-[var(--bd)] text-[var(--tx7)] hover:border-purple-500/40'
                }`}>
                {new Date(r.created_at).toLocaleDateString()} {i === 0 && '(latest)'}
              </button>
            ))}
          </div>
        )}

        <div className="p-5">
          {!reports ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={22} className="text-purple-400 animate-spin" />
            </div>
          ) : reports.length === 0 ? (
            <p className="text-[var(--tx7)] text-sm text-center py-8">No guided-discovery sessions resolved yet for this concept.</p>
          ) : active?.status === 'pending' ? (
            <div className="flex flex-col items-center justify-center gap-2 py-12">
              <Loader2 size={22} className="text-purple-400 animate-spin" />
              <p className="text-[var(--tx7)] text-xs">Generating report…</p>
              <p className="text-[var(--tx8)] text-[10px]">Usually takes about 10-15 seconds — this updates automatically</p>
            </div>
          ) : active?.status === 'failed' ? (
            <p className="text-red-400 text-sm text-center py-8">Report generation failed{active.error_message ? `: ${active.error_message}` : '.'}</p>
          ) : active?.report ? (
            <div className="space-y-5">
              <p className="text-[var(--tx8)] text-[11px]">Resolved in {active.steps} guided step{active.steps === 1 ? '' : 's'} · {new Date(active.created_at).toLocaleString()}</p>

              {/* Academic Understanding */}
              <div className="border-l-2 border-purple-500 pl-4">
                <p className="text-[10px] text-[var(--tx8)] uppercase tracking-wider mb-1">Academic Understanding</p>
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-[var(--tx1)] text-base font-bold">{active.report.academic_understanding.level}</span>
                </div>
                <p className="text-[var(--tx3)] text-sm leading-relaxed">{active.report.academic_understanding.summary}</p>
              </div>

              {/* Thinking Radar */}
              <div>
                <p className="text-[10px] text-[var(--tx8)] uppercase tracking-wider mb-2">Thinking Radar — how they thought</p>
                <div className="grid sm:grid-cols-2 gap-3">
                  {DIMENSION_LABELS.map(([key, label]) => (
                    <RadarCard key={key} label={label} dim={active.report!.thinking_radar[key]} />
                  ))}
                </div>
              </div>

              {/* Strengths / Growth / Next steps */}
              <div className="grid sm:grid-cols-3 gap-4">
                <div>
                  <p className="text-[10px] text-green-400 uppercase tracking-wider mb-1.5 font-semibold">Strengths</p>
                  <BulletList items={active.report.strengths} color="bg-green-400" />
                </div>
                <div>
                  <p className="text-[10px] text-amber-400 uppercase tracking-wider mb-1.5 font-semibold">Areas for Growth</p>
                  <BulletList items={active.report.areas_for_growth} color="bg-amber-400" />
                </div>
                <div>
                  <p className="text-[10px] text-purple-400 uppercase tracking-wider mb-1.5 font-semibold">Next Steps</p>
                  <BulletList items={active.report.next_steps} color="bg-purple-400" />
                </div>
              </div>

              {/* Teacher Insight */}
              <div className="bg-purple-500/8 border border-purple-500/20 rounded-xl p-4 flex items-start gap-2.5">
                <Lightbulb size={15} className="text-purple-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-[10px] text-purple-400 uppercase tracking-wider font-semibold mb-1">Teacher Insight</p>
                  <p className="text-[var(--tx2)] text-sm leading-relaxed">{active.report.teacher_insight}</p>
                </div>
              </div>

              {/* Suggested next topic */}
              <div className="grid sm:grid-cols-2 gap-3">
                <div className="border border-[var(--bd)] rounded-xl p-3.5">
                  <p className="text-[10px] text-[var(--tx8)] uppercase tracking-wider mb-1.5 flex items-center gap-1">
                    <TrendingUp size={10} /> Suggested Next Topic
                  </p>
                  <p className="text-[var(--tx2)] text-xs leading-relaxed">{active.report.suggested_next_topic}</p>
                </div>
                <div className="border border-[var(--bd)] rounded-xl p-3.5">
                  <p className="text-[10px] text-[var(--tx8)] uppercase tracking-wider mb-1.5 flex items-center gap-1">
                    <ArrowUpRight size={10} /> Optional Extension
                  </p>
                  <p className="text-[var(--tx2)] text-xs leading-relaxed">{active.report.optional_extension}</p>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
