'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  MessageSquare, Video, BookOpen, BarChart2, Settings,
  Plus, ChevronRight, ChevronLeft, Search, Menu, X,
} from 'lucide-react';
import { useTranslation } from '@/hooks/useTranslation';
import { useSessionStore } from '@/store/sessionStore';
import { listConversations } from '@/lib/api';

interface SidebarProps {
  /** ID of the currently-open conversation (highlights it in the list) */
  selectedConversationId?: string;
  /** Called when the user clicks "+ New chat" */
  onNewChat: () => void;
  /** Called when the user clicks a past conversation (only needed on the chat page) */
  onConversationSelect?: (id: string) => void;
}

const SUBJECT_ICONS: Record<string, string> = {
  Mathematics: '📐', Physics: '⚛️', Chemistry: '🧪', Biology: '🧬',
  'Computer Science': '💻', History: '📜', Geography: '🌍', Economics: '📈',
  Literature: '📖', Philosophy: '🤔', Psychology: '🧠', Engineering: '⚙️',
  'Medicine & Health': '🏥', Business: '💼', Music: '🎵', Law: '⚖️',
  Other: '📚',
};

export function Sidebar({ selectedConversationId, onNewChat, onConversationSelect }: SidebarProps) {
  // Default closed — user must explicitly open it
  const [expanded, setExpanded] = useState(false);
  const [search,   setSearch]   = useState('');
  const pathname = usePathname();
  const router   = useRouter();
  const { t }    = useTranslation();
  const {
    user, token, sessionId,
    conversations, setConversations,
    activeConversationId,
  } = useSessionStore();

  // ── Fetch / refresh conversation list whenever auth state changes ───────────
  useEffect(() => {
    if (user?.id) {
      listConversations(user.id, undefined, token ?? undefined)
        .then(setConversations)
        .catch(() => {});
    } else if (sessionId) {
      listConversations(undefined, sessionId)
        .then(setConversations)
        .catch(() => {});
    }
  }, [user?.id, sessionId]);

  // Close sidebar on mobile when the route changes (navigation)
  useEffect(() => {
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setExpanded(false);
    }
  }, [pathname]);

  // ── Clicking a conversation: navigate to home then load it ─────────────────
  function handleConvClick(id: string) {
    // Auto-close on mobile after selecting a conversation
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setExpanded(false);
    }
    if (onConversationSelect) {
      // We're already on the chat page — load inline
      onConversationSelect(id);
    } else {
      // We're on another page — go home; home page will auto-restore via activeConversationId
      useSessionStore.getState().setActiveConversationId(id);
      router.push('/');
    }
  }

  function handleNewChat() {
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setExpanded(false);
    }
    onNewChat();
  }

  const filtered = conversations.filter(c =>
    !search || c.title?.toLowerCase().includes(search.toLowerCase())
  );

  // Group by date
  const now       = new Date();
  const todayStr  = now.toDateString();
  const yesterStr = new Date(Date.now() - 86400000).toDateString();

  const groups: Record<string, typeof conversations> = { today: [], yesterday: [], week: [], older: [] };
  for (const c of filtered) {
    const d = new Date(c.updated_at).toDateString();
    if      (d === todayStr)                                                         groups.today.push(c);
    else if (d === yesterStr)                                                        groups.yesterday.push(c);
    else if (Date.now() - new Date(c.updated_at).getTime() < 7 * 86400000)         groups.week.push(c);
    else                                                                             groups.older.push(c);
  }

  const activeId = selectedConversationId ?? activeConversationId ?? undefined;

  return (
    <>
      {/* ── Mobile: backdrop — click outside to close ─────────────────────── */}
      {expanded && (
        <div
          className="fixed inset-0 bg-black/60 z-40 md:hidden"
          onClick={() => setExpanded(false)}
          aria-hidden="true"
        />
      )}

      {/* ── Mobile: floating hamburger button — visible when sidebar is closed ─ */}
      {!expanded && (
        <button
          className="fixed top-3.5 left-3.5 z-50 md:hidden w-9 h-9 flex items-center justify-center rounded-lg bg-[#1a1a1a] border border-white/10 text-white/50 hover:text-white transition-colors"
          onClick={() => setExpanded(true)}
          aria-label="Open menu"
        >
          <Menu size={18} />
        </button>
      )}

      {/*
        ── Sidebar panel ─────────────────────────────────────────────────────
        Mobile  : fixed overlay — slides in from left, sits on top of chat
        Desktop : relative flex item — collapses to icon strip (w-14)
      */}
      <aside
        className={[
          // Positioning
          'fixed md:relative inset-y-0 left-0',
          'z-50 md:z-auto',
          // Layout
          'flex flex-col shrink-0',
          // Appearance
          'bg-[#0f0f0f] border-r border-white/10',
          // Smooth open/close
          'transition-all duration-300 ease-in-out',
          // Width & transform per state
          expanded
            ? 'translate-x-0 w-64'
            : '-translate-x-full md:translate-x-0 w-64 md:w-14',
        ].join(' ')}
      >

        {/* ── Header ────────────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-3 py-4 border-b border-white/10 shrink-0">
          {expanded && <span className="text-white font-bold text-sm tracking-wide">Learn-AI</span>}
          <button
            onClick={() => setExpanded(e => !e)}
            className="text-white/50 hover:text-white transition-colors ml-auto"
            aria-label={expanded ? 'Collapse sidebar' : 'Expand sidebar'}
          >
            {expanded ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
          </button>
        </div>

        {/* ── Nav items ─────────────────────────────────────────────────────── */}
        <nav className="px-2 py-2 space-y-1 shrink-0">
          {/* New chat */}
          <button
            onClick={handleNewChat}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-white/70 hover:text-white hover:bg-white/10 transition-colors text-sm"
          >
            <span className="shrink-0"><Plus size={18} /></span>
            {expanded && <span>{t.sidebar.newChat}</span>}
          </button>

          {/* Nav links */}
          {[
            { icon: <Video size={18} />,     label: t.sidebar.myVideos,  href: '/videos'   },
            { icon: <BookOpen size={18} />,  label: t.sidebar.studySets, href: '/study'    },
            { icon: <BarChart2 size={18} />, label: t.sidebar.progress,  href: '/progress' },
            { icon: <Settings size={18} />,  label: t.sidebar.settings,  href: '/settings' },
          ].map(({ icon, label, href }) => (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors text-sm ${
                pathname === href
                  ? 'bg-white/15 text-white'
                  : 'text-white/70 hover:text-white hover:bg-white/10'
              }`}
            >
              <span className="shrink-0">{icon}</span>
              {expanded && <span>{label}</span>}
            </Link>
          ))}
        </nav>

        {/* ── Conversation history — only when expanded ──────────────────────── */}
        {expanded && (
          <>
            <div className="px-3 py-2 shrink-0">
              <div className="flex items-center gap-2 bg-white/5 rounded-lg px-3 py-1.5">
                <Search size={13} className="text-white/40" />
                <input
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder={t.sidebar.searchConversations}
                  className="bg-transparent text-white/80 text-xs outline-none w-full placeholder-white/30"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto no-scrollbar px-2 pb-4 space-y-4 text-xs">
              {Object.entries({
                today:     t.sidebar.today,
                yesterday: t.sidebar.yesterday,
                week:      t.sidebar.lastWeek,
                older:     t.sidebar.older,
              }).map(([key, label]) =>
                groups[key].length > 0 && (
                  <div key={key}>
                    <p className="px-3 py-1 text-white/30 text-[10px] uppercase tracking-widest">{label}</p>
                    {groups[key].map(c => (
                      <button
                        key={c.id}
                        onClick={() => handleConvClick(c.id)}
                        className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 transition-colors text-left ${
                          activeId === c.id ? 'bg-white/15' : ''
                        }`}
                      >
                        <span className="text-sm shrink-0">
                          {c.subject
                            ? (SUBJECT_ICONS[c.subject] ?? '📚')
                            : <MessageSquare size={13} className="text-white/40" />}
                        </span>
                        <span className="text-white/70 truncate">{c.title || 'New conversation'}</span>
                      </button>
                    ))}
                  </div>
                )
              )}
              {filtered.length === 0 && (
                <p className="px-3 text-white/30">{t.sidebar.noConversations}</p>
              )}
            </div>
          </>
        )}

        {/* ── User badge at bottom ───────────────────────────────────────────── */}
        {expanded && user && (
          <div className="px-3 py-3 border-t border-white/10 shrink-0">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-purple-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
                {user.email[0].toUpperCase()}
              </div>
              <div className="overflow-hidden">
                <p className="text-white/80 text-xs truncate">{user.email}</p>
                <p className="text-white/40 text-[10px] capitalize">{user.tier}</p>
              </div>
            </div>
          </div>
        )}
      </aside>
    </>
  );
}
