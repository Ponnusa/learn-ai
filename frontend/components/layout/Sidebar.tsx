'use client';
import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  MessageSquare, Video, BookOpen, BarChart2, Settings,
  Plus, ChevronRight, ChevronLeft, Search,
} from 'lucide-react';
import { useTranslation } from '@/hooks/useTranslation';
import { useSessionStore } from '@/store/sessionStore';

interface Conversation {
  id: string;
  title: string;
  subject?: string;
  subtopic?: string;
  updated_at: string;
}

interface SidebarProps {
  conversations?: Conversation[];
  onNewChat: () => void;
}

const SUBJECT_ICONS: Record<string, string> = {
  Mathematics: '📐', Physics: '⚛️', Chemistry: '🧪', Biology: '🧬',
  'Computer Science': '💻', History: '📜', Geography: '🌍', Economics: '📈',
  Literature: '📖', Philosophy: '🤔', Psychology: '🧠', Engineering: '⚙️',
  'Medicine & Health': '🏥', Business: '💼', Music: '🎵', Law: '⚖️',
  Other: '📚',
};

export function Sidebar({ conversations = [], onNewChat }: SidebarProps) {
  const [expanded, setExpanded] = useState(true);
  const [search, setSearch] = useState('');
  const pathname = usePathname();
  const { t } = useTranslation();
  const { user } = useSessionStore();

  const navItems = [
    { icon: <Plus size={18} />,        label: t.sidebar.newChat,      onClick: onNewChat,  action: true },
    { icon: <Video size={18} />,       label: t.sidebar.myVideos,     href: '/videos' },
    { icon: <BookOpen size={18} />,    label: t.sidebar.studySets,    href: '/study' },
    { icon: <BarChart2 size={18} />,   label: t.sidebar.progress,     href: '/progress' },
    { icon: <Settings size={18} />,    label: t.sidebar.settings,     href: '/settings' },
  ];

  const filtered = conversations.filter(c =>
    !search || c.title?.toLowerCase().includes(search.toLowerCase())
  );

  // Group by date
  const now = new Date();
  const todayStr = now.toDateString();
  const yesterStr = new Date(now.setDate(now.getDate() - 1)).toDateString();

  const groups: Record<string, Conversation[]> = { today: [], yesterday: [], week: [], older: [] };
  for (const c of filtered) {
    const d = new Date(c.updated_at).toDateString();
    if (d === todayStr)                                       groups.today.push(c);
    else if (d === yesterStr)                                 groups.yesterday.push(c);
    else if (Date.now() - new Date(c.updated_at).getTime() < 7 * 86400000) groups.week.push(c);
    else                                                      groups.older.push(c);
  }

  return (
    <aside className={`flex flex-col h-screen bg-[#0f0f0f] border-r border-white/10 transition-all duration-200 ${expanded ? 'w-64' : 'w-14'} shrink-0`}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-4 border-b border-white/10">
        {expanded && (
          <span className="text-white font-bold text-sm tracking-wide">Learn-AI</span>
        )}
        <button
          onClick={() => setExpanded(e => !e)}
          className="text-white/50 hover:text-white transition-colors ml-auto"
        >
          {expanded ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
        </button>
      </div>

      {/* Nav items */}
      <nav className="px-2 py-2 space-y-1">
        {navItems.map((item, i) => (
          item.action ? (
            <button
              key={i}
              onClick={item.onClick}
              className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-white/70 hover:text-white hover:bg-white/10 transition-colors text-sm"
            >
              <span className="shrink-0">{item.icon}</span>
              {expanded && <span>{item.label}</span>}
            </button>
          ) : (
            <Link
              key={i}
              href={item.href!}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors text-sm ${
                pathname === item.href
                  ? 'bg-white/15 text-white'
                  : 'text-white/70 hover:text-white hover:bg-white/10'
              }`}
            >
              <span className="shrink-0">{item.icon}</span>
              {expanded && <span>{item.label}</span>}
            </Link>
          )
        ))}
      </nav>

      {/* Conversation history — only when expanded */}
      {expanded && (
        <>
          <div className="px-3 py-2">
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

          <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-4 text-xs">
            {Object.entries({ today: t.sidebar.today, yesterday: t.sidebar.yesterday, week: t.sidebar.lastWeek, older: t.sidebar.older }).map(([key, label]) => (
              groups[key].length > 0 && (
                <div key={key}>
                  <p className="px-3 py-1 text-white/30 text-[10px] uppercase tracking-widest">{label}</p>
                  {groups[key].map(c => (
                    <Link
                      key={c.id}
                      href={`/chat/${c.id}`}
                      className={`flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 transition-colors ${
                        pathname === `/chat/${c.id}` ? 'bg-white/15' : ''
                      }`}
                    >
                      <span className="text-sm shrink-0">
                        {c.subject ? (SUBJECT_ICONS[c.subject] ?? '📚') : <MessageSquare size={13} className="text-white/40" />}
                      </span>
                      <span className="text-white/70 truncate">{c.title || 'New conversation'}</span>
                    </Link>
                  ))}
                </div>
              )
            ))}
            {filtered.length === 0 && (
              <p className="px-3 text-white/30">{t.sidebar.noConversations}</p>
            )}
          </div>
        </>
      )}

      {/* User badge at bottom */}
      {expanded && user && (
        <div className="px-3 py-3 border-t border-white/10">
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
  );
}
