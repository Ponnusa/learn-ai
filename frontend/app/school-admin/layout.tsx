'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  LayoutDashboard, GraduationCap, Layers, Users,
  BookOpen, Mail, Settings, ExternalLink, Menu, X, School,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface SchoolInfo { name: string; code: string; }

const NAV = [
  { href: '/school-admin/dashboard', icon: LayoutDashboard, label: 'Dashboard'  },
  { href: '/school-admin/teachers',  icon: GraduationCap,   label: 'Teachers'   },
  { href: '/school-admin/sections',  icon: Layers,          label: 'Sections'   },
  { href: '/school-admin/students',  icon: Users,           label: 'Students'   },
  { href: '/school-admin/courses',   icon: BookOpen,        label: 'Courses'    },
  { href: '/school-admin/invites',   icon: Mail,            label: 'Invites'    },
];

export default function SchoolAdminLayout({ children }: { children: React.ReactNode }) {
  const router   = useRouter();
  const pathname = usePathname();
  const { user, token } = useSessionStore();
  const [school,   setSchool]   = useState<SchoolInfo | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (!user) { router.replace('/auth/teacher'); return; }
    if (!['institution_admin', 'super_admin'].includes(user.account_type ?? '')) {
      router.replace('/'); return;
    }
    fetch(`${API}/api/school/context`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.school) setSchool(d.school); })
      .catch(() => {});
  }, [user]);

  // close mobile sidebar on route change
  useEffect(() => { setMobileOpen(false); }, [pathname]);

  function NavLink({ href, icon: Icon, label }: typeof NAV[0]) {
    const active = pathname === href || pathname.startsWith(href + '/');
    return (
      <Link
        href={href}
        className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors
          ${active
            ? 'bg-purple-600/20 text-purple-300'
            : 'text-[var(--tx5)] hover:text-[var(--tx1)] hover:bg-[var(--ov3)]'
          }`}
      >
        <Icon size={17} className={active ? 'text-purple-400' : ''} />
        {label}
      </Link>
    );
  }

  function SidebarContent() {
    return (
      <div className="flex flex-col h-full">
        {/* School header */}
        <div className="px-4 py-5 border-b border-[var(--bd)]">
          <div className="flex items-center gap-2.5 mb-1">
            <School size={18} className="text-purple-400 shrink-0" />
            <span className="text-[var(--tx1)] font-semibold text-sm truncate">
              {school?.name ?? 'School Admin'}
            </span>
          </div>
          {school?.code && (
            <span className="inline-block text-xs px-2 py-0.5 rounded-full bg-purple-600/20 text-purple-300 font-mono">
              {school.code}
            </span>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 flex flex-col gap-1 overflow-y-auto">
          {NAV.map(item => <NavLink key={item.href} {...item} />)}
          <div className="mt-2 border-t border-[var(--bd)] pt-2">
            <NavLink href="/school-admin/settings" icon={Settings} label="Settings" />
          </div>
        </nav>

        {/* Bottom: open platform */}
        <div className="px-3 pb-4 border-t border-[var(--bd)] pt-3">
          <a
            href="https://www.learnx-ai.com/institution/dashboard"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-[var(--tx5)]
                       hover:text-[var(--tx1)] hover:bg-[var(--ov3)] transition-colors"
          >
            <ExternalLink size={17} />
            Open Platform
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">

      {/* Desktop sidebar */}
      <aside className="hidden md:flex flex-col w-56 shrink-0 bg-[var(--surface)] border-r border-[var(--bd)] h-full">
        <SidebarContent />
      </aside>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside
        className={`fixed left-0 top-0 z-50 h-full w-56 bg-[var(--surface)] border-r border-[var(--bd)]
          flex flex-col md:hidden transition-transform duration-300
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="flex items-center justify-between px-4 h-14 border-b border-[var(--bd)] shrink-0">
          <span className="text-[var(--tx1)] font-semibold text-sm">School Admin</span>
          <button onClick={() => setMobileOpen(false)} className="text-[var(--tx5)] hover:text-[var(--tx1)]">
            <X size={18} />
          </button>
        </div>
        <SidebarContent />
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Mobile top bar */}
        <div className="md:hidden flex items-center h-14 px-4 border-b border-[var(--bd)] bg-[var(--bg)] shrink-0">
          <button onClick={() => setMobileOpen(true)} className="text-[var(--tx5)] hover:text-[var(--tx1)]">
            <Menu size={18} />
          </button>
          <span className="ml-3 text-[var(--tx1)] font-semibold text-sm">
            {school?.name ?? 'School Admin'}
          </span>
        </div>
        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
      </main>
    </div>
  );
}
