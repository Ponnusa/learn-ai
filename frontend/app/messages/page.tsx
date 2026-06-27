'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { MessageSquare, Loader2 } from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';
import { Sidebar, MobileTopBar } from '@/components/layout/Sidebar';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Thread {
  id: string; name: string; email: string;
  last_message: string | null; last_message_at: string | null; unread_count: number;
}

export default function MessagesPage() {
  const router = useRouter();
  const { user, token } = useSessionStore();

  const [threads, setThreads] = useState<Thread[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) { router.replace('/auth/login'); return; }
    load();
  }, [user]);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/messages/threads`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setThreads(await res.json());
    } finally { setLoading(false); }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
      <Sidebar onNewChat={() => router.push('/')} />
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <MobileTopBar />
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex-1 flex items-center justify-center h-full">
              <Loader2 size={28} className="text-purple-400 animate-spin" />
            </div>
          ) : (
            <div className="p-6 max-w-2xl mx-auto">
              <div className="mb-6">
                <h1 className="text-[var(--tx1)] text-2xl font-bold">Messages</h1>
                <p className="text-[var(--tx6)] text-sm mt-1">
                  {user?.account_type === 'teacher' || user?.account_type === 'institution_admin' || user?.account_type === 'super_admin'
                    ? 'Direct messages with your students' : 'Direct messages with your teachers'}
                </p>
              </div>

              {threads.length === 0 ? (
                <div className="text-center py-20">
                  <div className="w-16 h-16 rounded-2xl bg-[var(--ov2)] flex items-center justify-center mx-auto mb-4">
                    <MessageSquare size={28} className="text-[var(--tx7)]" />
                  </div>
                  <p className="text-[var(--tx3)] font-medium mb-1">No conversations yet</p>
                  <p className="text-[var(--tx7)] text-sm">Messages with your classroom contacts will show up here</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {threads.map(th => (
                    <button key={th.id} onClick={() => router.push(`/messages/${th.id}`)}
                      className="w-full text-left flex items-center gap-3 bg-[var(--surface)] border border-[var(--bd)]
                                 hover:border-purple-500/30 rounded-2xl p-4 transition-all">
                      <div className="w-9 h-9 rounded-full bg-purple-600/20 flex items-center justify-center shrink-0">
                        <span className="text-purple-400 text-xs font-bold">{(th.name ?? th.email)[0].toUpperCase()}</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-[var(--tx1)] text-sm font-medium truncate">{th.name ?? th.email}</p>
                          {th.unread_count > 0 && (
                            <span className="text-[10px] bg-red-500 text-white rounded-full min-w-[16px] h-4 px-1 flex items-center justify-center font-bold">
                              {th.unread_count}
                            </span>
                          )}
                        </div>
                        <p className="text-[var(--tx7)] text-xs truncate">{th.last_message ?? 'No messages yet'}</p>
                      </div>
                      {th.last_message_at && (
                        <span className="text-[var(--tx8)] text-xs shrink-0">{new Date(th.last_message_at).toLocaleDateString()}</span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
