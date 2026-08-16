'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Sidebar, MobileTopBar } from '@/components/layout/Sidebar';
import { useTranslation } from '@/hooks/useTranslation';
import {
  Info, Video, BookOpen, GraduationCap, Users, BarChart2,
  Brain, Sparkles, ClipboardList, FileText, Shield, Mail,
  ExternalLink,
} from 'lucide-react';

const DEMO_VIDEOS = [
  { url: 'https://pub-ca784163fe614f62b1a3ebb8fe9ad1d3.r2.dev/promo/Teacher_New.mp4', titleKey: 0 },
  { url: 'https://pub-ca784163fe614f62b1a3ebb8fe9ad1d3.r2.dev/promo/Video%20Project%203.mp4', titleKey: 1 },
] as const;

const STUDENT_ICONS = [Brain, Video, Sparkles, BookOpen, BarChart2];
const TEACHER_ICONS = [BookOpen, Video, Users, BarChart2, ClipboardList];

// Guide files per language (falls back to English if no translated version exists)
const GUIDE_LOCALES: Partial<Record<string, string>> = {
  fi: 'fi', sv: 'sv',
};
function guideHref(base: string, lang: string) {
  const loc = GUIDE_LOCALES[lang];
  return loc ? `/docs/${base}-${loc}.html` : `/docs/${base}.html`;
}

export default function InfoPage() {
  const router = useRouter();
  const { t, language } = useTranslation();
  const ti = t.info;
  const [activeRole, setActiveRole] = useState<'student' | 'teacher'>('student');
  const features = activeRole === 'student' ? ti.studentFeatures : ti.teacherFeatures;
  const icons = activeRole === 'student' ? STUDENT_ICONS : TEACHER_ICONS;

  const GUIDES = [
    { base: 'student-manual', icon: GraduationCap, color: 'from-purple-500 to-indigo-600' },
    { base: 'teacher-manual', icon: BookOpen,      color: 'from-teal-500 to-cyan-600'     },
    { base: 'admin-manual',   icon: Users,         color: 'from-amber-500 to-orange-600'  },
  ];

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
      <Sidebar onNewChat={() => router.push('/')} />
      <main className="flex-1 flex flex-col overflow-hidden">
        <MobileTopBar />
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 pb-16">

            {/* Header */}
            <div className="flex items-center gap-3 mb-10">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-500 to-cyan-600 flex items-center justify-center shrink-0">
                <Info size={20} className="text-white" />
              </div>
              <div>
                <h1 className="text-[var(--tx1)] text-xl font-bold">{ti.title}</h1>
                <p className="text-[var(--tx6)] text-sm">{ti.subtitle}</p>
              </div>
            </div>

            {/* ── What you can do ────────────────────────────────────────── */}
            <section className="mb-10">
              <h2 className="text-[var(--tx6)] font-semibold text-xs uppercase tracking-widest mb-4">{ti.whatYouCanDo}</h2>

              <div className="flex gap-1 mb-5 bg-[var(--surface)] border border-[var(--bd)] rounded-xl p-1 w-fit">
                <button
                  onClick={() => setActiveRole('student')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
                    activeRole === 'student'
                      ? 'bg-purple-600 text-white shadow-sm'
                      : 'text-[var(--tx5)] hover:text-[var(--tx2)]'
                  }`}
                >
                  <GraduationCap size={13} /> {ti.forStudents}
                </button>
                <button
                  onClick={() => setActiveRole('teacher')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
                    activeRole === 'teacher'
                      ? 'bg-teal-600 text-white shadow-sm'
                      : 'text-[var(--tx5)] hover:text-[var(--tx2)]'
                  }`}
                >
                  <BookOpen size={13} /> {ti.forTeachers}
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {features.map((f, i) => {
                  const Icon = icons[i];
                  return (
                    <div key={i} className="flex gap-3 p-4 rounded-xl bg-[var(--surface)] border border-[var(--bd)] hover:border-[var(--bd2)] transition-colors">
                      <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
                        activeRole === 'student' ? 'bg-purple-500/15 text-purple-400' : 'bg-teal-500/15 text-teal-400'
                      }`}>
                        <Icon size={18} />
                      </div>
                      <div className="min-w-0">
                        <p className="text-[var(--tx1)] text-sm font-medium mb-0.5">{f.title}</p>
                        <p className="text-[var(--tx5)] text-xs leading-relaxed">{f.desc}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            {/* ── Demo Videos ───────────────────────────────────────────── */}
            <section className="mb-10">
              <h2 className="text-[var(--tx6)] font-semibold text-xs uppercase tracking-widest mb-4">{ti.seeItInAction}</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {DEMO_VIDEOS.map(({ url, titleKey }) => (
                  <div key={url} className="rounded-xl overflow-hidden border border-[var(--bd)] bg-[var(--surface)]">
                    <div className="relative bg-black aspect-video">
                      <video src={url} controls preload="metadata" className="w-full h-full object-contain" />
                    </div>
                    <div className="px-4 py-3 flex items-center gap-2">
                      <Video size={14} className="text-[var(--tx6)] shrink-0" />
                      <span className="text-[var(--tx3)] text-sm font-medium">{ti.videoTitles[titleKey]}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* ── User Guides ───────────────────────────────────────────── */}
            <section className="mb-10">
              <h2 className="text-[var(--tx6)] font-semibold text-xs uppercase tracking-widest mb-4">{ti.userGuides}</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {GUIDES.map(({ base, icon: Icon, color }, i) => (
                  <a
                    key={base}
                    href={guideHref(base, language)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group flex flex-col gap-3 p-4 rounded-xl bg-[var(--surface)] border border-[var(--bd)] hover:border-[var(--bd2)] hover:shadow-sm transition-all"
                  >
                    <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${color} flex items-center justify-center text-white shrink-0`}>
                      <Icon size={20} />
                    </div>
                    <div>
                      <div className="flex items-center gap-1.5 mb-1">
                        <p className="text-[var(--tx1)] text-sm font-semibold">{ti.guides[i].role}</p>
                        <ExternalLink size={11} className="text-[var(--tx7)] opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                      <p className="text-[var(--tx5)] text-xs leading-relaxed">{ti.guides[i].desc}</p>
                    </div>
                    <div className="flex items-center gap-1 text-xs text-[var(--tx6)] mt-auto">
                      <FileText size={11} /> {ti.openGuide}
                    </div>
                  </a>
                ))}
              </div>
            </section>

            {/* ── About ─────────────────────────────────────────────────── */}
            <section>
              <h2 className="text-[var(--tx6)] font-semibold text-xs uppercase tracking-widest mb-4">{ti.about}</h2>
              <div className="rounded-2xl bg-[var(--surface)] border border-[var(--bd)] overflow-hidden">
                <div className="p-5 border-b border-[var(--bd3)]">
                  <div className="flex items-start gap-3">
                    <img src="/logo-36.png" alt="LearnX-AI" className="w-10 h-10 object-contain rounded-xl shrink-0" />
                    <div>
                      <p className="text-[var(--tx1)] font-semibold text-sm">LearnX-AI</p>
                      <p className="text-[var(--tx5)] text-xs mt-0.5">{ti.platformDesc}</p>
                      <p className="text-[var(--tx6)] text-xs mt-2">NordX Labs Oy · Business ID: 3615236-4 · Espoo, Finland</p>
                    </div>
                  </div>
                </div>

                <div className="divide-y divide-[var(--bd3)]">
                  <div className="flex items-center justify-between px-5 py-3.5">
                    <div className="flex items-center gap-2 text-[var(--tx4)] text-sm">
                      <Mail size={14} className="text-[var(--tx6)]" /> Support
                    </div>
                    <a href="mailto:hello@animlearn.com" className="text-purple-400 hover:text-purple-300 text-sm transition-colors">
                      hello@animlearn.com
                    </a>
                  </div>
                  <div className="flex items-center justify-between px-5 py-3.5">
                    <div className="flex items-center gap-2 text-[var(--tx4)] text-sm">
                      <Shield size={14} className="text-[var(--tx6)]" /> Legal
                    </div>
                    <div className="flex items-center gap-3">
                      <Link href="/privacy" className="text-[var(--tx5)] hover:text-[var(--tx1)] text-sm transition-colors">Privacy Policy</Link>
                      <Link href="/terms" className="text-[var(--tx5)] hover:text-[var(--tx1)] text-sm transition-colors">Terms of Service</Link>
                    </div>
                  </div>
                </div>

                <div className="px-5 py-4 bg-[var(--ov1)]">
                  <p className="text-[var(--tx7)] text-xs leading-relaxed">{ti.disclaimer}</p>
                </div>
              </div>
            </section>

          </div>
        </div>
      </main>
    </div>
  );
}
