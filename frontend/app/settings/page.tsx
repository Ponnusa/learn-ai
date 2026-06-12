'use client';
import { useState } from 'react';
import { Settings, LogOut, User, Shield, Bell, Palette, Sun, Moon } from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { useRouter } from 'next/navigation';
import { useSessionStore } from '@/store/sessionStore';
import { useTheme } from '@/hooks/useTheme';

export default function SettingsPage() {
  const router = useRouter();
  const { user, signOut } = useSessionStore();
  const { theme, setTheme } = useTheme();
  const [confirmSignOut, setConfirmSignOut] = useState(false);

  function handleSignOut() {
    signOut();
    router.replace('/');
  }

  const sections = [
    {
      title: 'Account',
      icon: <User size={16} className="text-purple-500" />,
      items: user
        ? [
            { label: 'Email',        value: user.email },
            { label: 'Display name', value: user.name || '(not set)' },
            { label: 'Account tier', value: user.tier },
          ]
        : [],
    },
    {
      title: 'Privacy & Security',
      icon: <Shield size={16} className="text-blue-500" />,
      items: [
        { label: 'Anonymous session data', value: 'Cleared on browser close' },
        { label: 'Conversation history',   value: 'Stored on our servers' },
      ],
    },
    {
      title: 'Notifications',
      icon: <Bell size={16} className="text-amber-500" />,
      items: [
        { label: 'Email updates', value: 'Coming soon' },
      ],
    },
  ];

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
      <Sidebar onNewChat={() => router.push('/')} />
      <main className="flex-1 chat-scroll bg-[var(--bg)] p-8 pt-14 md:pt-8">
        <div className="max-w-xl mx-auto">

          {/* Page header */}
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-slate-500 to-slate-600 flex items-center justify-center">
              <Settings size={20} className="text-white" />
            </div>
            <div>
              <h1 className="text-[var(--tx1)] text-xl font-bold">Settings</h1>
              <p className="text-[var(--tx6)] text-sm">Manage your account and preferences</p>
            </div>
          </div>

          {/* Sign-in nudge (anonymous user) */}
          {!user && (
            <div className="mb-6 rounded-2xl bg-purple-500/10 border border-purple-500/20 p-5 flex items-center justify-between">
              <div>
                <p className="text-[var(--tx1)] font-medium text-sm">You're not signed in</p>
                <p className="text-[var(--tx6)] text-xs mt-0.5">Sign in to manage your account settings</p>
              </div>
              <button
                onClick={() => router.push('/auth/login')}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl font-medium transition-all shrink-0"
              >
                Sign in
              </button>
            </div>
          )}

          <div className="space-y-4">
            {/* ── Appearance (theme toggle) ─────────────────────────────── */}
            <div className="rounded-2xl bg-[var(--surface)] border border-[var(--bd)] overflow-hidden">
              <div className="flex items-center gap-2 px-5 py-3 border-b border-[var(--bd2)]">
                <Palette size={16} className="text-violet-500" />
                <span className="text-[var(--tx6)] text-xs font-medium uppercase tracking-wider">Appearance</span>
              </div>
              <div className="flex items-center justify-between px-5 py-4">
                <div>
                  <p className="text-[var(--tx2)] text-sm font-medium">Theme</p>
                  <p className="text-[var(--tx6)] text-xs mt-0.5">Choose your preferred appearance</p>
                </div>
                {/* Segmented toggle */}
                <div className="flex items-center gap-1 bg-[var(--input)] rounded-xl p-1 border border-[var(--bd)]">
                  <button
                    onClick={() => setTheme('light')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                      theme === 'light'
                        ? 'bg-purple-600 text-white shadow-sm'
                        : 'text-[var(--tx5)] hover:text-[var(--tx2)]'
                    }`}
                  >
                    <Sun size={13} /> Light
                  </button>
                  <button
                    onClick={() => setTheme('dark')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                      theme === 'dark'
                        ? 'bg-purple-600 text-white shadow-sm'
                        : 'text-[var(--tx5)] hover:text-[var(--tx2)]'
                    }`}
                  >
                    <Moon size={13} /> Dark
                  </button>
                </div>
              </div>
            </div>

            {/* ── Account / Privacy / Notifications ─────────────────────── */}
            {sections.map((section, si) =>
              section.items.length > 0 && (
                <div key={si} className="rounded-2xl bg-[var(--surface)] border border-[var(--bd)] overflow-hidden">
                  <div className="flex items-center gap-2 px-5 py-3 border-b border-[var(--bd2)]">
                    {section.icon}
                    <span className="text-[var(--tx6)] text-xs font-medium uppercase tracking-wider">{section.title}</span>
                  </div>
                  {section.items.map((item, ii) => (
                    <div key={ii} className="flex items-center justify-between px-5 py-3.5 border-b border-[var(--bd3)] last:border-0">
                      <span className="text-[var(--tx3)] text-sm">{item.label}</span>
                      <span className="text-[var(--tx7)] text-sm">{item.value}</span>
                    </div>
                  ))}
                </div>
              )
            )}
          </div>

          {/* Sign out */}
          {user && (
            <div className="mt-6">
              {!confirmSignOut ? (
                <button
                  onClick={() => setConfirmSignOut(true)}
                  className="w-full flex items-center justify-center gap-2 py-3 rounded-xl
                             border border-[var(--wrong-bd)] bg-[var(--wrong-bg)]
                             text-[var(--red)] hover:bg-red-500/10 text-sm font-medium transition-all"
                >
                  <LogOut size={15} /> Sign out
                </button>
              ) : (
                <div className="rounded-xl border border-[var(--wrong-bd)] bg-[var(--wrong-bg)] p-4 text-center">
                  <p className="text-[var(--tx1)] text-sm mb-3">Sign out of Learn-AI?</p>
                  <div className="flex gap-2 justify-center">
                    <button
                      onClick={() => setConfirmSignOut(false)}
                      className="px-4 py-2 rounded-lg bg-[var(--ov3)] hover:bg-[var(--ov4)] text-[var(--tx3)] text-sm transition-all"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleSignOut}
                      className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm font-medium transition-all"
                    >
                      Sign out
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

        </div>
      </main>
    </div>
  );
}
