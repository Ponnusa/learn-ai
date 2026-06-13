'use client';
import { useEffect, useState } from 'react';
import { BarChart2, MessageSquare, Video, HelpCircle, BookOpen, Star, Calendar, Image } from 'lucide-react';
import { Sidebar, MobileTopBar } from '@/components/layout/Sidebar';
import { useRouter } from 'next/navigation';
import { useSessionStore } from '@/store/sessionStore';
import { getUserStats, getUserLimits } from '@/lib/api';

// ─── Types ────────────────────────────────────────────────────────────────────

type UserStats = {
  messages:      number;
  videos:        number;
  quizzes:       number;
  conversations: number;
  top_subject:   string | null;
  member_since:  string | null;
};

type UserLimits = {
  tier: string;
  limits: {
    messages_daily: number;
    videos_daily:   number;
    images_daily:   number;
    quiz_daily:     number;
  };
  usage_today: {
    messages: number;
    videos:   number;
    images:   number;
    quizzes:  number;
  };
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatMemberSince(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en', { month: 'long', year: 'numeric' });
}

function capitalize(s: string | null): string {
  if (!s) return '—';
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function tierColor(tier: string) {
  if (tier === 'pro')     return 'bg-amber-500/15 text-amber-400 border-amber-500/30';
  if (tier === 'learner') return 'bg-blue-500/15 text-blue-400 border-blue-500/30';
  return 'bg-[var(--ov3)] text-[var(--tx5)] border-[var(--bd)]';
}

// ─── Stat card ────────────────────────────────────────────────────────────────

function StatCard({
  icon, label, value, bg, loading,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  bg: string;
  loading?: boolean;
}) {
  return (
    <div className={`rounded-2xl border p-5 flex flex-col gap-3 ${bg}`}>
      <div className="w-9 h-9 rounded-xl bg-white/5 flex items-center justify-center">
        {icon}
      </div>
      {loading ? (
        <div className="h-8 w-16 rounded-lg bg-white/10 animate-pulse" />
      ) : (
        <p className="text-[var(--tx1)] text-2xl font-bold">{value}</p>
      )}
      <p className="text-[var(--tx6)] text-xs">{label}</p>
    </div>
  );
}

// ─── Usage row ────────────────────────────────────────────────────────────────

function UsageRow({
  icon, label, used, limit, iconBg, loading,
}: {
  icon: React.ReactNode;
  label: string;
  used: number;
  limit: number;
  iconBg: string;
  loading?: boolean;
}) {
  const unlimited = limit === -1;
  const pct       = unlimited ? 100 : Math.min(100, limit === 0 ? 100 : (used / limit) * 100);
  const nearLimit = !unlimited && pct >= 80;

  return (
    <div className="flex items-center gap-3">
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${iconBg}`}>
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between mb-1.5">
          <span className="text-[var(--tx3)] text-xs font-medium">{label}</span>
          {loading ? (
            <div className="h-3 w-20 rounded bg-[var(--ov3)] animate-pulse" />
          ) : (
            <span className={`text-xs tabular-nums ${nearLimit ? 'text-red-400' : 'text-[var(--tx6)]'}`}>
              {unlimited ? `${used} used · Unlimited` : `${used} / ${limit} today`}
            </span>
          )}
        </div>
        <div className="h-1.5 rounded-full bg-[var(--ov3)] overflow-hidden">
          {loading ? (
            <div className="h-full w-1/3 rounded-full bg-[var(--ov5)] animate-pulse" />
          ) : unlimited ? (
            <div className="h-full rounded-full bg-emerald-500/50" style={{ width: '100%' }} />
          ) : (
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                nearLimit ? 'bg-red-500' : 'bg-purple-500'
              }`}
              style={{ width: `${pct}%` }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ProgressPage() {
  const router                          = useRouter();
  const { user, token, msgCount, videoCount, quizCount } = useSessionStore();

  const [stats,        setStats]        = useState<UserStats | null>(null);
  const [limitsData,   setLimitsData]   = useState<UserLimits | null>(null);
  const [loading,      setLoading]      = useState(false);
  const [limitsLoading,setLimitsLoading]= useState(false);
  const [error,        setError]        = useState<string | null>(null);

  useEffect(() => {
    if (!user?.id) return;
    setLoading(true);
    setLimitsLoading(true);
    setError(null);

    getUserStats(user.id, token ?? undefined)
      .then(s  => { setStats(s); setLoading(false); })
      .catch(() => { setError('Could not load stats. Try refreshing.'); setLoading(false); });

    getUserLimits(user.id, token ?? undefined)
      .then(l  => { setLimitsData(l); setLimitsLoading(false); })
      .catch(() => setLimitsLoading(false));
  }, [user?.id]);

  // ── Stat cards config ──────────────────────────────────────────────────────
  const statCards = user && stats !== null
    ? [
        {
          icon:  <MessageSquare size={18} className="text-purple-400" />,
          label: 'Messages sent',
          value: stats.messages,
          bg:    'bg-purple-500/10 border-purple-500/20',
        },
        {
          icon:  <BookOpen size={18} className="text-sky-400" />,
          label: 'Conversations',
          value: stats.conversations,
          bg:    'bg-sky-500/10 border-sky-500/20',
        },
        {
          icon:  <Video size={18} className="text-blue-400" />,
          label: 'Videos created',
          value: stats.videos,
          bg:    'bg-blue-500/10 border-blue-500/20',
        },
        {
          icon:  <HelpCircle size={18} className="text-indigo-400" />,
          label: 'Quizzes completed',
          value: stats.quizzes,
          bg:    'bg-indigo-500/10 border-indigo-500/20',
        },
      ]
    : [
        {
          icon:  <MessageSquare size={18} className="text-purple-400" />,
          label: 'Messages this session',
          value: msgCount,
          bg:    'bg-purple-500/10 border-purple-500/20',
        },
        {
          icon:  <Video size={18} className="text-blue-400" />,
          label: 'Videos this session',
          value: videoCount,
          bg:    'bg-blue-500/10 border-blue-500/20',
        },
        {
          icon:  <HelpCircle size={18} className="text-indigo-400" />,
          label: 'Quizzes this session',
          value: quizCount,
          bg:    'bg-indigo-500/10 border-indigo-500/20',
        },
      ];

  const u = limitsData?.usage_today;
  const l = limitsData?.limits;

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
      <Sidebar onNewChat={() => router.push('/')} />

      <main className="flex-1 flex flex-col bg-[var(--bg)]">
        <MobileTopBar />
        <div className="flex-1 chat-scroll p-6 sm:p-8">
        <div className="max-w-2xl mx-auto">

          {/* Header */}
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-green-600 to-emerald-600
                            flex items-center justify-center shadow-lg shadow-green-500/20">
              <BarChart2 size={20} className="text-white" />
            </div>
            <div>
              <h1 className="text-[var(--tx1)] text-xl font-bold">Your Progress</h1>
              <p className="text-[var(--tx6)] text-sm">
                {user ? 'Lifetime activity from your account' : 'Session activity overview'}
              </p>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="mb-6 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20
                            text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Stats grid */}
          <div className={`grid gap-4 mb-6 ${user ? 'grid-cols-2 sm:grid-cols-4' : 'grid-cols-3'}`}>
            {statCards.map((s, i) => (
              <StatCard key={i} {...s} loading={loading} />
            ))}
          </div>

          {/* Plan & Daily Usage — logged-in only */}
          {user && (
            <div className="rounded-2xl border border-[var(--bd)] bg-[var(--surface)] p-5 mb-6">
              <div className="flex items-center justify-between mb-5">
                <p className="text-[var(--tx2)] text-sm font-semibold">Plan & Daily Usage</p>
                {limitsLoading ? (
                  <div className="h-5 w-20 rounded-full bg-[var(--ov3)] animate-pulse" />
                ) : (
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
                    tierColor(limitsData?.tier ?? '')
                  }`}>
                    {capitalize(limitsData?.tier ?? null)} Plan
                  </span>
                )}
              </div>
              <div className="space-y-4">
                <UsageRow
                  icon={<MessageSquare size={14} className="text-purple-400" />}
                  label="Messages"
                  used={u?.messages ?? 0}
                  limit={l?.messages_daily ?? 0}
                  iconBg="bg-purple-500/10"
                  loading={limitsLoading}
                />
                <UsageRow
                  icon={<Video size={14} className="text-blue-400" />}
                  label="Videos"
                  used={u?.videos ?? 0}
                  limit={l?.videos_daily ?? 0}
                  iconBg="bg-blue-500/10"
                  loading={limitsLoading}
                />
                <UsageRow
                  icon={<Image size={14} className="text-pink-400" />}
                  label="Diagrams"
                  used={u?.images ?? 0}
                  limit={l?.images_daily ?? 0}
                  iconBg="bg-pink-500/10"
                  loading={limitsLoading}
                />
                <UsageRow
                  icon={<HelpCircle size={14} className="text-indigo-400" />}
                  label="Quizzes"
                  used={u?.quizzes ?? 0}
                  limit={l?.quiz_daily ?? 0}
                  iconBg="bg-indigo-500/10"
                  loading={limitsLoading}
                />
              </div>
              <p className="text-[var(--tx6)] text-[11px] mt-4">Resets every 24 hours.</p>
            </div>
          )}

          {/* Extra info row for logged-in users */}
          {user && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
              {/* Top subject */}
              <div className="rounded-2xl border border-[var(--bd)] bg-[var(--surface)] p-5 flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20
                                flex items-center justify-center shrink-0">
                  <Star size={18} className="text-amber-400" />
                </div>
                <div className="min-w-0">
                  <p className="text-[var(--tx6)] text-xs mb-0.5">Favourite subject</p>
                  {loading
                    ? <div className="h-5 w-24 rounded bg-[var(--ov3)] animate-pulse" />
                    : <p className="text-[var(--tx1)] font-semibold text-sm">
                        {capitalize(stats?.top_subject ?? null)}
                      </p>
                  }
                </div>
              </div>

              {/* Member since */}
              <div className="rounded-2xl border border-[var(--bd)] bg-[var(--surface)] p-5 flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20
                                flex items-center justify-center shrink-0">
                  <Calendar size={18} className="text-emerald-400" />
                </div>
                <div className="min-w-0">
                  <p className="text-[var(--tx6)] text-xs mb-0.5">Member since</p>
                  {loading
                    ? <div className="h-5 w-28 rounded bg-[var(--ov3)] animate-pulse" />
                    : <p className="text-[var(--tx1)] font-semibold text-sm">
                        {formatMemberSince(stats?.member_since ?? null)}
                      </p>
                  }
                </div>
              </div>
            </div>
          )}

          {/* Sign-in CTA for anonymous users */}
          {!user && (
            <div className="rounded-2xl bg-[var(--surface)] border border-[var(--bd)] p-6 text-center mb-6">
              <p className="text-[var(--tx1)] font-medium mb-1">Sign in to track long-term progress</p>
              <p className="text-[var(--tx6)] text-sm mb-4">
                Lifetime stats, favourite subject, and more — available for registered users.
              </p>
              <button
                onClick={() => router.push('/auth/login')}
                className="px-5 py-2.5 bg-purple-600 hover:bg-purple-500 text-white text-sm
                           rounded-xl font-medium transition-all"
              >
                Sign in free
              </button>
            </div>
          )}

          {/* Coming soon panel */}
          <div className="rounded-2xl bg-[var(--surface)] border border-[var(--bd)] p-6 text-center">
            <p className="text-[var(--tx5)] text-sm">
              Detailed subject breakdowns, streaks, and learning milestones — coming soon.
            </p>
          </div>

        </div>
        </div>
      </main>
    </div>
  );
}
