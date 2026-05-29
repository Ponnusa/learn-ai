'use client';
import { useEffect, useState } from 'react';
import { BarChart2, MessageSquare, Video, HelpCircle, BookOpen, Star, Calendar, Loader } from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { useRouter } from 'next/navigation';
import { useSessionStore } from '@/store/sessionStore';
import { getUserStats } from '@/lib/api';

// ─── Types ────────────────────────────────────────────────────────────────────

type UserStats = {
  messages:      number;
  videos:        number;
  quizzes:       number;
  conversations: number;
  top_subject:   string | null;
  member_since:  string | null;
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

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ProgressPage() {
  const router                          = useRouter();
  const { user, token, msgCount, videoCount, quizCount } = useSessionStore();

  const [stats,   setStats]   = useState<UserStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);

  // Fetch real stats from DB when logged in
  useEffect(() => {
    if (!user?.id) return;
    setLoading(true);
    setError(null);
    getUserStats(user.id, token ?? undefined)
      .then(s  => { setStats(s); setLoading(false); })
      .catch(() => { setError('Could not load stats. Try refreshing.'); setLoading(false); });
  }, [user?.id]);

  // ── Stat cards config ────────────────────────────────────────────────────────
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

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
      <Sidebar onNewChat={() => router.push('/')} />

      <main className="flex-1 overflow-y-auto no-scrollbar bg-[var(--bg)] p-6 sm:p-8">
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
              📈 Detailed subject breakdowns, streaks, and learning milestones — coming soon.
            </p>
          </div>

        </div>
      </main>
    </div>
  );
}
