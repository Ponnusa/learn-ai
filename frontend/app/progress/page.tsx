'use client';
import { BarChart2, MessageSquare, Video, HelpCircle } from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { useRouter } from 'next/navigation';
import { useSessionStore } from '@/store/sessionStore';

export default function ProgressPage() {
  const router = useRouter();
  const { user, msgCount, videoCount, quizCount } = useSessionStore();

  const stats = [
    { icon: <MessageSquare size={20} className="text-purple-400" />, label: 'Messages sent',    value: msgCount,    bg: 'bg-purple-500/10 border-purple-500/20' },
    { icon: <Video         size={20} className="text-blue-400"   />, label: 'Videos generated', value: videoCount,  bg: 'bg-blue-500/10 border-blue-500/20'     },
    { icon: <HelpCircle    size={20} className="text-indigo-400" />, label: 'Quizzes taken',    value: quizCount,   bg: 'bg-indigo-500/10 border-indigo-500/20' },
  ];

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar onNewChat={() => router.push('/')} />
      <main className="flex-1 overflow-y-auto no-scrollbar bg-[#0f0f0f] p-8">
        <div className="max-w-2xl mx-auto">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-green-600 to-emerald-600 flex items-center justify-center shadow-lg shadow-green-500/20">
              <BarChart2 size={20} className="text-white" />
            </div>
            <div>
              <h1 className="text-white text-xl font-bold">Your Progress</h1>
              <p className="text-white/40 text-sm">Session activity overview</p>
            </div>
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-3 gap-4 mb-8">
            {stats.map((s, i) => (
              <div key={i} className={`rounded-2xl border p-5 ${s.bg}`}>
                <div className="mb-3">{s.icon}</div>
                <p className="text-white text-2xl font-bold">{s.value}</p>
                <p className="text-white/40 text-xs mt-1">{s.label}</p>
              </div>
            ))}
          </div>

          {/* Upsell / sign-in prompt */}
          {!user ? (
            <div className="rounded-2xl bg-[#1a1a1a] border border-white/10 p-6 text-center">
              <p className="text-white font-medium mb-1">Sign in to track long-term progress</p>
              <p className="text-white/40 text-sm mb-4">Detailed analytics, streaks, and subject breakdowns are available for registered users.</p>
              <button onClick={() => router.push('/auth/login')}
                className="px-5 py-2.5 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl font-medium transition-all">
                Sign in free
              </button>
            </div>
          ) : (
            <div className="rounded-2xl bg-[#1a1a1a] border border-white/10 p-6 text-center text-white/40 text-sm">
              Detailed subject analytics and learning streaks are coming soon.
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
