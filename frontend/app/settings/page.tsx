'use client';
import { useState } from 'react';
import { Settings, LogOut, User, Shield, Bell, ChevronRight } from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { useRouter } from 'next/navigation';
import { useSessionStore } from '@/store/sessionStore';

export default function SettingsPage() {
  const router = useRouter();
  const { user, signOut } = useSessionStore();
  const [confirmSignOut, setConfirmSignOut] = useState(false);

  function handleSignOut() {
    signOut();
    router.replace('/');
  }

  const sections = [
    {
      title: 'Account',
      icon: <User size={16} className="text-purple-400" />,
      items: user
        ? [
            { label: 'Email',         value: user.email,                      action: false },
            { label: 'Display name',  value: user.name || '(not set)',        action: false },
            { label: 'Account tier',  value: user.tier,                       action: false },
          ]
        : [],
    },
    {
      title: 'Privacy & Security',
      icon: <Shield size={16} className="text-blue-400" />,
      items: [
        { label: 'Anonymous session data', value: 'Cleared on browser close', action: false },
        { label: 'Conversation history',   value: 'Stored on our servers',     action: false },
      ],
    },
    {
      title: 'Notifications',
      icon: <Bell size={16} className="text-amber-400" />,
      items: [
        { label: 'Email updates', value: 'Coming soon', action: false },
      ],
    },
  ];

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar onNewChat={() => router.push('/')} />
      <main className="flex-1 overflow-y-auto bg-[#0f0f0f] p-8">
        <div className="max-w-xl mx-auto">

          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-slate-600 to-slate-700 flex items-center justify-center">
              <Settings size={20} className="text-white" />
            </div>
            <div>
              <h1 className="text-white text-xl font-bold">Settings</h1>
              <p className="text-white/40 text-sm">Manage your account and preferences</p>
            </div>
          </div>

          {!user && (
            <div className="mb-6 rounded-2xl bg-purple-600/10 border border-purple-500/25 p-5 flex items-center justify-between">
              <div>
                <p className="text-white font-medium text-sm">You're not signed in</p>
                <p className="text-white/40 text-xs mt-0.5">Sign in to manage your account settings</p>
              </div>
              <button onClick={() => router.push('/auth/login')}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl font-medium transition-all shrink-0">
                Sign in
              </button>
            </div>
          )}

          <div className="space-y-4">
            {sections.map((section, si) => (
              section.items.length > 0 && (
                <div key={si} className="rounded-2xl bg-[#1a1a1a] border border-white/10 overflow-hidden">
                  <div className="flex items-center gap-2 px-5 py-3 border-b border-white/[0.06]">
                    {section.icon}
                    <span className="text-white/60 text-xs font-medium uppercase tracking-wider">{section.title}</span>
                  </div>
                  {section.items.map((item, ii) => (
                    <div key={ii} className="flex items-center justify-between px-5 py-3.5 border-b border-white/[0.04] last:border-0">
                      <span className="text-white/70 text-sm">{item.label}</span>
                      <span className="text-white/35 text-sm">{item.value}</span>
                    </div>
                  ))}
                </div>
              )
            ))}
          </div>

          {/* Sign out */}
          {user && (
            <div className="mt-6">
              {!confirmSignOut ? (
                <button
                  onClick={() => setConfirmSignOut(true)}
                  className="w-full flex items-center justify-center gap-2 py-3 rounded-xl border border-red-500/20 bg-red-500/5 text-red-400 hover:bg-red-500/10 text-sm font-medium transition-all"
                >
                  <LogOut size={15} /> Sign out
                </button>
              ) : (
                <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-center">
                  <p className="text-white text-sm mb-3">Sign out of Learn-AI?</p>
                  <div className="flex gap-2 justify-center">
                    <button onClick={() => setConfirmSignOut(false)}
                      className="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/15 text-white/70 text-sm transition-all">
                      Cancel
                    </button>
                    <button onClick={handleSignOut}
                      className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm font-medium transition-all">
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
