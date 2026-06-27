'use client';
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  MessageSquare, Video, BookOpen, BarChart2, Settings,
  Search, Menu, X, PenSquare, User, Sparkles, Users, LayoutDashboard, GraduationCap, ClipboardList, Mail,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';
import { listConversations } from '@/lib/api';
import { useTranslation } from '@/hooks/useTranslation';

// Module-level callback so MobileTopBar (rendered anywhere) can open the sidebar panel
let _openMobile: (() => void) | null = null;

/** Inline hamburger + logo bar — place it as the first child of a scrollable container
 *  so it scrolls away naturally as the user reads content. md:hidden keeps it off desktop. */
export function MobileTopBar() {
  return (
    <div className="md:hidden flex items-center h-14 px-3 border-b border-[var(--bd)] bg-[var(--bg)] shrink-0">
      <button
        onClick={() => _openMobile?.()}
        aria-label="Open menu"
        className="w-9 h-9 flex items-center justify-center rounded-lg
                   text-[var(--tx5)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)] transition-colors"
      >
        <Menu size={18} />
      </button>
      <div className="flex-1 flex justify-center">
        <img src="/logo-36.png" alt="LearnAI" className="w-8 h-8 object-contain" />
      </div>
      <div className="w-9" />
    </div>
  );
}

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

/*
 * Module-level flag: when the user clicks the Chats icon from a non-home page,
 * we push to '/' and signal the newly-mounted Sidebar to auto-open the panel.
 */
let pendingOpenChats = false;

export function Sidebar({ selectedConversationId, onNewChat, onConversationSelect }: SidebarProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [chatsOpen,  setChatsOpen]  = useState(false);
  const [search,     setSearch]     = useState('');
  const searchRef = useRef<HTMLInputElement>(null);
  const pathname  = usePathname();
  const router    = useRouter();
  const { t } = useTranslation();
  const {
    user, token, sessionId,
    conversations, setConversations,
    activeConversationId,
  } = useSessionStore();

  // ── Register module-level open callback for MobileTopBar ─────────────────
  useEffect(() => {
    _openMobile = () => setMobileOpen(true);
    return () => { _openMobile = null; };
  }, []);

  // ── Poll unread direct-message count (teacher <-> student) ───────────────
  const [unreadMessages, setUnreadMessages] = useState(0);
  useEffect(() => {
    if (!user) return;
    let stopped = false;
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    async function poll() {
      try {
        const res = await fetch(`${API_BASE}/api/messages/unread-count`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!stopped && res.ok) setUnreadMessages((await res.json()).unread_count ?? 0);
      } catch { /* ignore */ }
      if (!stopped) setTimeout(poll, 20000);
    }
    poll();
    return () => { stopped = true; };
  }, [user, token]);

  // ── Auto-open chats panel when navigated here from another page ──────────
  useEffect(() => {
    if (pendingOpenChats && onConversationSelect) {
      setChatsOpen(true);
      pendingOpenChats = false;
    }
  }, [onConversationSelect]);

  // ── Fetch conversation list ───────────────────────────────────────────────
  useEffect(() => {
    if (user?.id) {
      listConversations(user.id, undefined, token ?? undefined)
        .then(setConversations).catch(() => {});
    } else if (sessionId) {
      listConversations(undefined, sessionId)
        .then(setConversations).catch(() => {});
    }
  }, [user?.id, sessionId]);

  // ── Focus search & clear on open/close ───────────────────────────────────
  useEffect(() => {
    if (chatsOpen) {
      setTimeout(() => searchRef.current?.focus(), 80);
    } else {
      setSearch('');
    }
  }, [chatsOpen]);

  // ── Close mobile panel on route change ───────────────────────────────────
  useEffect(() => {
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setMobileOpen(false);
    }
  }, [pathname]);

  // ── Handlers ─────────────────────────────────────────────────────────────
  function handleChatsClick() {
    if (onConversationSelect) {
      setChatsOpen(c => !c);            // on home page — toggle panel
    } else {
      pendingOpenChats = true;           // signal home page to open panel
      router.push('/');
    }
  }

  function handleConvClick(id: string) {
    if (typeof window !== 'undefined' && window.innerWidth < 768) setMobileOpen(false);
    if (onConversationSelect) {
      onConversationSelect(id);
    } else {
      useSessionStore.getState().setActiveConversationId(id);
      router.push('/');
    }
  }

  function handleNewChat() {
    if (typeof window !== 'undefined' && window.innerWidth < 768) setMobileOpen(false);
    setChatsOpen(false);
    onNewChat();
  }

  // ── Filter + group conversations ─────────────────────────────────────────
  const q = search.toLowerCase();
  const filtered = conversations.filter(c =>
    !q ||
    c.title?.toLowerCase().includes(q) ||
    c.subject?.toLowerCase().includes(q) ||
    c.study_set_title?.toLowerCase().includes(q)
  );

  // Split: study-set-linked vs regular
  const studySetConvs = filtered.filter(c => c.study_set_id);
  const regularConvs  = filtered.filter(c => !c.study_set_id);

  // Group study-set conversations by study_set_id
  type StudyGroup = { study_set_id: string; title: string; count: number; updated_at: string };
  const studyGroupMap = new Map<string, StudyGroup>();
  for (const c of studySetConvs) {
    const existing = studyGroupMap.get(c.study_set_id!);
    if (!existing) {
      studyGroupMap.set(c.study_set_id!, {
        study_set_id: c.study_set_id!,
        title:        c.study_set_title || c.title,
        count:        1,
        updated_at:   c.updated_at,
      });
    } else {
      existing.count++;
      if (c.updated_at > existing.updated_at) existing.updated_at = c.updated_at;
    }
  }
  const studyGroups = Array.from(studyGroupMap.values())
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at));

  // Date-group regular conversations
  const now       = new Date();
  const todayStr  = now.toDateString();
  const yesterStr = new Date(Date.now() - 86400000).toDateString();

  const groups: Record<string, typeof regularConvs> = {
    today: [], yesterday: [], week: [], older: [],
  };
  for (const c of regularConvs) {
    const d = new Date(c.updated_at).toDateString();
    if      (d === todayStr)                                                  groups.today.push(c);
    else if (d === yesterStr)                                                 groups.yesterday.push(c);
    else if (Date.now() - new Date(c.updated_at).getTime() < 7 * 86400000)  groups.week.push(c);
    else                                                                      groups.older.push(c);
  }

  function fmtDate(iso: string) {
    const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
    if (diff === 0) return 'Today';
    if (diff === 1) return 'Yesterday';
    if (diff < 7)  return `${diff}d ago`;
    return new Date(iso).toLocaleDateString('en', { month: 'short', day: 'numeric' });
  }

  const activeId = selectedConversationId ?? activeConversationId ?? undefined;

  const isTeacher  = ['teacher', 'institution_admin'].includes(user?.account_type ?? '');
  const isSuperAdmin = user?.account_type === 'super_admin';

  const navItems = [
    ...(isTeacher
      ? [{ icon: <LayoutDashboard size={18} />, label: 'Dashboard', href: '/teacher/dashboard' }]
      : []),
    ...(isSuperAdmin
      ? [{ icon: <LayoutDashboard size={18} />, label: 'Admin', href: '/admin' }]
      : []),
    { icon: <Video size={18} />,     label: t.sidebar.myVideos,  href: '/videos'   },
    { icon: <BookOpen size={18} />,  label: t.sidebar.studySets, href: '/study'    },
    { icon: <Sparkles size={18} />,  label: t.progress.diagrams, href: '/images'   },
    { icon: <BarChart2 size={18} />, label: t.sidebar.progress,  href: '/progress' },
    { icon: <Mail size={18} />, label: 'Messages', href: '/messages', badge: unreadMessages },
    ...(isTeacher || isSuperAdmin
      ? [
          { icon: <Users size={18} />,        label: 'Classrooms',     href: '/teacher/classrooms' },
          { icon: <BookOpen size={18} />,     label: 'Course Builder', href: '/teacher/courses'    },
          { icon: <GraduationCap size={18} />, label: 'Students',      href: '/teacher/students'   },
          { icon: <BarChart2 size={18} />,     label: 'Progress',      href: '/teacher/progress'   },
        ]
      : [
          { icon: <Users size={18} />,         label: 'Classrooms',  href: '/classrooms' },
          { icon: <ClipboardList size={18} />, label: 'Assignments', href: '/assignments' },
        ]),
    { icon: <Settings size={18} />,  label: t.sidebar.settings,  href: '/settings' },
  ];

  return (
    <>
      {/* ── Mobile: dark backdrop ─────────────────────────────────── */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 md:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Mobile top bar is now rendered inline by each page via MobileTopBar export */}

      {/*
        ══ Outer wrapper ═══════════════════════════════════════════════
        Mobile  : fixed overlay, slides in/out
        Desktop : static flex child (sits in the flex row permanently)
        ═══════════════════════════════════════════════════════════════
      */}
      <div
        className={[
          'fixed md:relative z-50 md:z-auto',
          'flex h-screen',
          'transition-transform duration-300 ease-in-out',
          mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0',
        ].join(' ')}
      >

        {/* ═══════════════════════════════════════════════════════════
            ICON RAIL  — always visible on desktop, 56 px wide
            ═══════════════════════════════════════════════════════════ */}
        <nav className="w-14 flex flex-col bg-[var(--surface)] border-r border-[var(--bd)] shrink-0 h-full">

          {/* Logo */}
          <div className="flex items-center justify-center h-14 border-b border-[var(--bd)] shrink-0">
            <div className="w-9 h-9 rounded-xl overflow-hidden shrink-0 shadow-md shadow-black/20">
              <img src="/logo-36.png" alt="Learn-AI" className="w-full h-full object-contain" />
            </div>
          </div>

          {/* Top actions */}
          <div className="flex flex-col items-center gap-1 px-2 pt-3 pb-1 shrink-0">
            {/* New chat */}
            <button
              onClick={handleNewChat}
              title="New chat"
              className="w-10 h-10 flex items-center justify-center rounded-xl
                         text-[var(--tx5)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)]
                         transition-colors"
            >
              <PenSquare size={18} />
            </button>

            {/* Chats panel toggle */}
            <button
              onClick={handleChatsClick}
              title="Conversations"
              className={`w-10 h-10 flex items-center justify-center rounded-xl transition-colors ${
                chatsOpen
                  ? 'bg-purple-600/20 text-[var(--purple)]'
                  : 'text-[var(--tx5)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)]'
              }`}
            >
              <MessageSquare size={18} />
            </button>
          </div>

          {/* Divider */}
          <div className="mx-3 my-1 border-t border-[var(--bd)] shrink-0" />

          {/* Nav links */}
          <div className="flex flex-col items-center gap-1 px-2 py-2 shrink-0">
            {navItems.map(({ icon, label, href, badge }) => (
              <Link
                key={href}
                href={href}
                title={label}
                className={`relative w-10 h-10 flex items-center justify-center rounded-xl transition-colors ${
                  pathname === href
                    ? 'bg-[var(--ov4)] text-[var(--tx1)]'
                    : 'text-[var(--tx5)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)]'
                }`}
              >
                {icon}
                {!!badge && (
                  <span className="absolute top-0.5 right-0.5 min-w-[16px] h-4 px-1 rounded-full
                                    bg-red-500 text-white text-[10px] font-bold flex items-center justify-center">
                    {badge > 9 ? '9+' : badge}
                  </span>
                )}
              </Link>
            ))}
          </div>

          {/* Spacer */}
          <div className="flex-1" />

          {/* User avatar / sign-in */}
          <div className="flex items-center justify-center px-2 py-3 border-t border-[var(--bd)] shrink-0">
            {user ? (
              <Link href="/settings" title={user.email}>
                <div className="w-8 h-8 rounded-full bg-purple-600 flex items-center justify-center
                                text-white text-xs font-bold
                                hover:ring-2 hover:ring-purple-500/50 transition-all">
                  {user.email[0].toUpperCase()}
                </div>
              </Link>
            ) : (
              <Link
                href="/auth/login"
                title="Sign in"
                className="w-10 h-10 flex items-center justify-center rounded-xl
                           text-[var(--tx5)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)]
                           transition-colors"
              >
                <User size={18} />
              </Link>
            )}
          </div>
        </nav>

        {/* ═══════════════════════════════════════════════════════════
            CONVERSATION PANEL — slides in next to the icon rail
            ═══════════════════════════════════════════════════════════ */}
        {chatsOpen && (
          <div className="w-72 flex flex-col bg-[var(--bg)] border-r border-[var(--bd)] h-full">

            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3.5 border-b border-[var(--bd)] shrink-0">
              <h2 className="text-[var(--tx1)] font-semibold text-sm tracking-tight">{t.sidebar.conversations}</h2>
              <button
                onClick={() => setChatsOpen(false)}
                className="w-6 h-6 flex items-center justify-center rounded-lg
                           text-[var(--tx6)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)]
                           transition-colors"
                aria-label="Close"
              >
                <X size={14} />
              </button>
            </div>

            {/* Search bar */}
            <div className="px-3 py-2.5 shrink-0">
              <div className="flex items-center gap-2 bg-[var(--surface)] rounded-xl px-3 py-2
                              border border-[var(--bd)] focus-within:border-purple-500/50
                              transition-colors">
                <Search size={13} className="text-[var(--tx6)] shrink-0" />
                <input
                  ref={searchRef}
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder={t.sidebar.searchConversations}
                  className="bg-transparent text-[var(--tx2)] text-xs outline-none w-full t-ph"
                />
                {search && (
                  <button
                    onClick={() => setSearch('')}
                    className="text-[var(--tx6)] hover:text-[var(--tx1)] shrink-0 transition-colors"
                    aria-label="Clear search"
                  >
                    <X size={11} />
                  </button>
                )}
              </div>
            </div>

            {/* Conversation list */}
            <div className="flex-1 chat-scroll px-2 pb-4 space-y-3 text-xs">

              {/* ── Study Sets group ──────────────────────────────────────── */}
              {studyGroups.length > 0 && (
                <div>
                  <p className="px-3 py-1.5 text-[var(--tx8)] text-[10px] uppercase tracking-widest font-medium">
                    {t.sidebar.studySets}
                  </p>
                  {studyGroups.map(g => (
                    <button
                      key={g.study_set_id}
                      onClick={() => { router.push(`/study/${g.study_set_id}?tab=chat`); setChatsOpen(false); if (typeof window !== 'undefined' && window.innerWidth < 768) setMobileOpen(false); }}
                      className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl
                                 hover:bg-[var(--ov3)] transition-colors text-left group"
                    >
                      <div className="w-6 h-6 rounded-lg bg-indigo-500/15 border border-indigo-500/20
                                      flex items-center justify-center shrink-0">
                        <BookOpen size={11} className="text-indigo-400" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-[var(--tx2)] truncate text-xs leading-snug font-medium">
                          {g.title}
                        </p>
                        <p className="text-[var(--tx7)] text-[10px] mt-0.5">
                          {g.count} chat{g.count !== 1 ? 's' : ''} · {fmtDate(g.updated_at)}
                        </p>
                      </div>
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-indigo-500/10
                                       text-indigo-400 border border-indigo-500/20 shrink-0 tabular-nums">
                        {g.count}
                      </span>
                    </button>
                  ))}
                </div>
              )}

              {/* ── Regular conversations — grouped by date ───────────────── */}
              {([
                ['today',     t.sidebar.today],
                ['yesterday', t.sidebar.yesterday],
                ['week',      t.sidebar.lastWeek],
                ['older',     t.sidebar.older],
              ] as [string, string][]).map(([key, label]) =>
                groups[key].length > 0 && (
                  <div key={key}>
                    <p className="px-3 py-1.5 text-[var(--tx8)] text-[10px] uppercase tracking-widest font-medium">
                      {label}
                    </p>
                    {groups[key].map(c => (
                      <button
                        key={c.id}
                        onClick={() => handleConvClick(c.id)}
                        className={`w-full flex items-start gap-2.5 px-3 py-2.5 rounded-xl
                                    hover:bg-[var(--ov3)] transition-colors text-left ${
                          activeId === c.id ? 'bg-[var(--ov4)]' : ''
                        }`}
                      >
                        <span className="text-sm shrink-0 mt-0.5 leading-none">
                          {c.subject
                            ? (SUBJECT_ICONS[c.subject] ?? '📚')
                            : <MessageSquare size={12} className="text-[var(--tx6)] mt-0.5" />}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-[var(--tx2)] truncate text-xs leading-snug">
                            {c.title || t.sidebar.newConversation}
                          </p>
                          {c.subject && (
                            <p className="text-[var(--tx7)] text-[10px] mt-0.5 truncate">{c.subject}</p>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                )
              )}

              {/* Empty states */}
              {conversations.length === 0 && (
                <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
                  <div className="w-12 h-12 rounded-2xl bg-[var(--ov2)] flex items-center justify-center mb-3">
                    <MessageSquare size={20} className="text-[var(--tx7)]" />
                  </div>
                  <p className="text-[var(--tx4)] text-xs font-medium">{t.sidebar.noConversations}</p>
                  <p className="text-[var(--tx8)] text-[10px] mt-1 leading-relaxed">
                    {t.sidebar.noConversationsHint}
                  </p>
                </div>
              )}
              {conversations.length > 0 && filtered.length === 0 && (
                <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
                  <div className="w-12 h-12 rounded-2xl bg-[var(--ov2)] flex items-center justify-center mb-3">
                    <Search size={20} className="text-[var(--tx7)]" />
                  </div>
                  <p className="text-[var(--tx4)] text-xs font-medium">{t.sidebar.noResults}</p>
                  <p className="text-[var(--tx8)] text-[10px] mt-1">
                    {t.sidebar.noResultsFor.replace('{search}', search)}
                  </p>
                </div>
              )}
            </div>

            {/* New chat CTA */}
            <div className="px-3 py-3 border-t border-[var(--bd)] shrink-0">
              <button
                onClick={handleNewChat}
                className="w-full flex items-center justify-center gap-2 py-2 rounded-xl
                           bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium
                           transition-colors"
              >
                <PenSquare size={13} /> {t.sidebar.newChat}
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
