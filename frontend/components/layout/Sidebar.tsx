'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  MessageSquare, Video, BookOpen, BarChart2, Settings,
  Plus, ChevronRight, ChevronLeft, Search, Menu,
} from 'lucide-react';
import { useTranslation } from '@/hooks/useTranslation';
import { useSessionStore } from '@/store/sessionStore';
import { listConversations } from '@/lib/api';

interface SidebarProps {
  selectedConversationId?: string;
  onNewChat: () => void;
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

  useEffect(() => {
    if (user?.id) {
      listConversations(user.id, undefined, token ?? undefined)
        .then(setConversations).catch(() => {});
    } else if (sessionId) {
      listConversations(undefined, sessionId)
        .then(setConversations).catch(() => {});
    }
  }, [user?.id, sessionId]);

  // Auto-close on mobile when route changes
  useEffect(() => {
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setExpanded(false);
    }
  }, [pathname]);

  function handleConvClick(id: string) {
    if (typeof window !== 'undefined' && window.innerWidth < 768) setExpanded(false);
    if (onConversationSelect) {
      onConversationSelect(id);
    } else {
      useSessionStore.getState().setActiveConversationId(id);
      router.push('/');
    }
  }

  function handleNewChat() {
    if (typeof window !== 'undefined' && window.innerWidth < 768) setExpanded(false);
    onNewChat();
  }

  const filtered = conversations.filter(c =>
    !search || c.title?.toLowerCase().includes(search.toLowerCase())
  );

  const now       = new Date();
  const todayStr  = now.toDateString();
  const yesterStr = new Date(Date.now() - 86400000).toDateString();
  const groups: Record<string, typeof conversations> = { today: [], yesterday: [], week: [], older: [] };
  for (const c of filtered) {
    const d = new Date(c.updated_at).toDateString();
    if      (d === todayStr)                                                  groups.today.push(c);
    else if (d === yesterStr)                                                 groups.yesterday.push(c);
    else if (Date.now() - new Date(c.updated_at).getTime() < 7 * 86400000)  groups.week.push(c);
    else                                                                      groups.older.push(c);
  }

  const activeId = selectedConversationId ?? activeConversationId ?? undefined;

  return (
    <>
      {/* Mobile backdrop */}
      {expanded && (
        <div
          className="fixed inset-0 bg-black/60 z-40 md:hidden"
          onClick={() => setExpanded(false)}
          aria-hidden="true"
        />
      )}

      {/* Mobile hamburger — shown when sidebar is closed */}
      {!expanded && (
        <button
          className="fixed top-3.5 left-3.5 z-50 md:hidden w-9 h-9 flex items-center justify-center
                     rounded-lg bg-[var(--surface)] border border-[var(--bd)]
                     text-[var(--tx5)] hover:text-[var(--tx1)] transition-colors"
          onClick={() => setExpanded(true)}
          aria-label="Open menu"
        >
          <Menu size={18} />
        </button>
      )}

      {/*
        Mobile  : fixed overlay — slides in from left, sits on top of chat
        Desktop : relative flex item — collapses to icon strip (w-14)
      */}
      <aside
        className={[
          'fixed md:relative inset-y-0 left-0 z-50 md:z-auto',
          'flex flex-col shrink-0',
          'bg-[var(--surface)] border-r border-[var(--bd)]',
          'transition-all duration-300 ease-in-out',
          expanded
            ? 'translate-x-0 w-64'
            : '-translate-x-full md:translate-x-0 w-64 md:w-14',
        ].join(' ')}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-4 border-b border-[var(--bd)] shrink-0">
          {expanded && <span className="text-[var(--tx1)] font-bold text-sm tracking-wide">Learn-AI</span>}
          <button
            onClick={() => setExpanded(e => !e)}
            className="text-[var(--tx6)] hover:text-[var(--tx1)] transition-colors ml-auto"
            aria-label={expanded ? 'Collapse sidebar' : 'Expand sidebar'}
          >
            {expanded ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
          </button>
        </div>

        {/* Nav items */}
        <nav className="px-2 py-2 space-y-1 shrink-0">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg
                       text-[var(--tx3)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)]
                       transition-colors text-sm"
          >
            <span className="shrink-0"><Plus size={18} /></span>
            {expanded && <span>{t.sidebar.newChat}</span>}
          </button>

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
                  ? 'bg-[var(--ov4)] text-[var(--tx1)]'
                  : 'text-[var(--tx3)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)]'
              }`}
            >
              <span className="shrink-0">{icon}</span>
              {expanded && <span>{label}</span>}
            </Link>
          ))}
        </nav>

        {/* Conversation history */}
        {expanded && (
          <>
            <div className="px-3 py-2 shrink-0">
              <div className="flex items-center gap-2 bg-[var(--ov1)] rounded-lg px-3 py-1.5">
                <Search size={13} className="text-[var(--tx6)]" />
                <input
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder={t.sidebar.searchConversations}
                  className="bg-transparent text-[var(--tx2)] text-xs outline-none w-full t-ph"
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
                    <p className="px-3 py-1 text-[var(--tx8)] text-[10px] uppercase tracking-widest">{label}</p>
                    {groups[key].map(c => (
                      <button
                        key={c.id}
                        onClick={() => handleConvClick(c.id)}
                        className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-[var(--ov3)] transition-colors text-left ${
                          activeId === c.id ? 'bg-[var(--ov4)]' : ''
                        }`}
                      >
                        <span className="text-sm shrink-0">
                          {c.subject
                            ? (SUBJECT_ICONS[c.subject] ?? '📚')
                            : <MessageSquare size={13} className="text-[var(--tx6)]" />}
                        </span>
                        <span className="text-[var(--tx3)] truncate">{c.title || 'New conversation'}</span>
                      </button>
                    ))}
                  </div>
                )
              )}
              {filtered.length === 0 && (
                <p className="px-3 text-[var(--tx8)]">{t.sidebar.noConversations}</p>
              )}
            </div>
          </>
        )}

        {/* User badge */}
        {expanded && user && (
          <div className="px-3 py-3 border-t border-[var(--bd)] shrink-0">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-purple-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
                {user.email[0].toUpperCase()}
              </div>
              <div className="overflow-hidden">
                <p className="text-[var(--tx2)] text-xs truncate">{user.email}</p>
                <p className="text-[var(--tx6)] text-[10px] capitalize">{user.tier}</p>
              </div>
            </div>
          </div>
        )}
      </aside>
    </>
  );
}
