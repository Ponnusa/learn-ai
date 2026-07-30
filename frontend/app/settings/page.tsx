'use client';
import { useState } from 'react';
import { Settings, LogOut, User, Shield, Bell, Palette, Sun, Moon, Globe } from 'lucide-react';
import { Sidebar, MobileTopBar } from '@/components/layout/Sidebar';
import { useRouter } from 'next/navigation';
import { useSessionStore } from '@/store/sessionStore';
import { useTheme } from '@/hooks/useTheme';
import { useLanguage } from '@/hooks/useLanguage';
import { useTranslation } from '@/hooks/useTranslation';
import { LANGUAGE_LABELS } from '@/translations';

export default function SettingsPage() {
  const router = useRouter();
  const { user, signOut } = useSessionStore();
  const { theme, setTheme } = useTheme();
  const { language, setLanguage, availableLanguages, institutionLanguages } = useLanguage();
  const { t } = useTranslation();
  const [confirmSignOut, setConfirmSignOut] = useState(false);

  function handleSignOut() {
    signOut();
    router.replace('/');
  }

  const locked = institutionLanguages?.length === 1;

  const sections = [
    {
      title: t.settings.account,
      icon: <User size={16} className="text-purple-500" />,
      items: user
        ? [
            { label: t.settings.emailField,   value: user.email },
            { label: t.settings.displayName,  value: user.name || t.settings.notSet },
            { label: t.settings.accountTier,  value: user.tier },
          ]
        : [],
    },
    {
      title: t.settings.privacySecurity,
      icon: <Shield size={16} className="text-blue-500" />,
      items: [
        { label: t.settings.anonymousSessionData, value: t.settings.clearedBrowserClose },
        { label: t.settings.conversationHistory,  value: t.settings.storedServers },
      ],
    },
    {
      title: t.settings.notifications,
      icon: <Bell size={16} className="text-amber-500" />,
      items: [
        { label: t.settings.emailUpdates, value: t.comingSoon },
      ],
    },
  ];

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
      <Sidebar onNewChat={() => router.push('/')} />
      <main className="flex-1 flex flex-col bg-[var(--bg)]">
        <MobileTopBar />
        <div className="flex-1 chat-scroll p-8">
        <div className="max-w-xl mx-auto">

          {/* Page header */}
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-slate-500 to-slate-600 flex items-center justify-center">
              <Settings size={20} className="text-white" />
            </div>
            <div>
              <h1 className="text-[var(--tx1)] text-xl font-bold">{t.settings.title}</h1>
              <p className="text-[var(--tx6)] text-sm">{t.settings.managePreferences}</p>
            </div>
          </div>

          {/* Sign-in nudge (anonymous user) */}
          {!user && (
            <div className="mb-6 rounded-2xl bg-purple-500/10 border border-purple-500/20 p-5 flex items-center justify-between">
              <div>
                <p className="text-[var(--tx1)] font-medium text-sm">{t.settings.notSignedIn}</p>
                <p className="text-[var(--tx6)] text-xs mt-0.5">{t.settings.signInToManage}</p>
              </div>
              <button
                onClick={() => router.push('/auth/login')}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl font-medium transition-all shrink-0"
              >
                {t.auth.signIn}
              </button>
            </div>
          )}

          <div className="space-y-4">
            {/* ── Appearance ────────────────────────────────────────────────── */}
            <div className="rounded-2xl bg-[var(--surface)] border border-[var(--bd)] overflow-hidden">
              <div className="flex items-center gap-2 px-5 py-3 border-b border-[var(--bd2)]">
                <Palette size={16} className="text-violet-500" />
                <span className="text-[var(--tx6)] text-xs font-medium uppercase tracking-wider">{t.settings.appearance}</span>
              </div>

              {/* Theme */}
              <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--bd3)]">
                <div>
                  <p className="text-[var(--tx2)] text-sm font-medium">{t.settings.theme}</p>
                  <p className="text-[var(--tx6)] text-xs mt-0.5">{t.settings.chooseAppearance}</p>
                </div>
                <div className="flex items-center gap-1 bg-[var(--input)] rounded-xl p-1 border border-[var(--bd)]">
                  <button
                    onClick={() => setTheme('light')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                      theme === 'light'
                        ? 'bg-purple-600 text-white shadow-sm'
                        : 'text-[var(--tx5)] hover:text-[var(--tx2)]'
                    }`}
                  >
                    <Sun size={13} /> {t.settings.light}
                  </button>
                  <button
                    onClick={() => setTheme('dark')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                      theme === 'dark'
                        ? 'bg-purple-600 text-white shadow-sm'
                        : 'text-[var(--tx5)] hover:text-[var(--tx2)]'
                    }`}
                  >
                    <Moon size={13} /> {t.settings.dark}
                  </button>
                </div>
              </div>

              {/* Language */}
              <div className="flex items-center justify-between px-5 py-4">
                <div className="flex items-center gap-2">
                  <Globe size={15} className="text-[var(--tx5)]" />
                  <div>
                    <p className="text-[var(--tx2)] text-sm font-medium">{t.settings.language}</p>
                    <p className="text-[var(--tx6)] text-xs mt-0.5">
                      {institutionLanguages
                        ? locked ? 'Set by your institution' : 'Restricted by your institution'
                        : t.settings.languageDesc}
                    </p>
                  </div>
                </div>
                <div className={`flex items-center gap-1 bg-[var(--input)] rounded-xl p-1 border border-[var(--bd)] ${locked ? 'opacity-60' : ''}`}>
                  {availableLanguages.map((lang) => (
                    <button
                      key={lang}
                      onClick={() => setLanguage(lang)}
                      disabled={locked}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                        language === lang
                          ? 'bg-purple-600 text-white shadow-sm'
                          : 'text-[var(--tx5)] hover:text-[var(--tx2)] disabled:cursor-not-allowed'
                      }`}
                    >
                      {LANGUAGE_LABELS[lang]}
                    </button>
                  ))}
                  {locked && (
                    <span className="text-[10px] text-purple-400 bg-purple-500/20 px-1.5 py-0.5 rounded-md ml-1">locked</span>
                  )}
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
                  <LogOut size={15} /> {t.auth.signOut}
                </button>
              ) : (
                <div className="rounded-xl border border-[var(--wrong-bd)] bg-[var(--wrong-bg)] p-4 text-center">
                  <p className="text-[var(--tx1)] text-sm mb-3">{t.settings.signOutConfirm}</p>
                  <div className="flex gap-2 justify-center">
                    <button
                      onClick={() => setConfirmSignOut(false)}
                      className="px-4 py-2 rounded-lg bg-[var(--ov3)] hover:bg-[var(--ov4)] text-[var(--tx3)] text-sm transition-all"
                    >
                      {t.cancel}
                    </button>
                    <button
                      onClick={handleSignOut}
                      className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm font-medium transition-all"
                    >
                      {t.auth.signOut}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

        </div>
        </div>
      </main>
    </div>
  );
}
