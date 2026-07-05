'use client';
import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  ArrowLeft, ChevronDown, ChevronRight,
  CheckCircle2, Circle, Loader2, BookOpen, Zap,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Concept {
  id: string;
  title: string;
  description?: string;
  study_set_id?: string;
  visited: boolean;
  quiz_score?: number;
}

interface Unit {
  id: string;
  title: string;
  description?: string;
  position: number;
  concepts: Concept[];
}

interface Course {
  id: string;
  name: string;
  description?: string;
  subject?: string;
  grade?: string;
  status: string;
  progress: { visited: number; total: number };
  units: Unit[];
}

export default function StudentCoursePage() {
  const router      = useRouter();
  const params      = useParams();
  const classroomId = params.id       as string;
  const courseId    = params.courseId as string;
  const { user, token } = useSessionStore();

  const [course,    setCourse]    = useState<Course | null>(null);
  const [loading,   setLoading]   = useState(true);
  const [expanded,  setExpanded]  = useState<Set<string>>(new Set());
  // concepts navigate to detail page — no activating state needed here

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    if (!user) { router.replace('/auth/login'); return; }
    load();
  }, [user, courseId]);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/courses/${courseId}/student`, { headers });
      if (!res.ok) { router.push(`/classrooms/${classroomId}`); return; }
      const data: Course = await res.json();
      setCourse(data);
      // Expand first unit by default
      if (data.units.length > 0) setExpanded(new Set([data.units[0].id]));
    } finally { setLoading(false); }
  }

  function toggleUnit(id: string) {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function openConcept(concept: Concept) {
    router.push(`/classrooms/${classroomId}/courses/${courseId}/concepts/${concept.id}`);
  }

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );

  if (!course) return null;

  const pct = course.progress.total > 0
    ? Math.round((course.progress.visited / course.progress.total) * 100)
    : 0;

  return (
    <div className="p-6 max-w-2xl mx-auto">
      {/* Back link */}
      <button onClick={() => router.push(`/classrooms/${classroomId}`)}
        className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm mb-6 transition-colors">
        <ArrowLeft size={15} /> Back to courses
      </button>

      {/* Course header */}
      <div className="mb-6">
        <h1 className="text-[var(--tx1)] text-2xl font-bold">{course.name}</h1>
        {course.description && (
          <p className="text-[var(--tx6)] text-sm mt-1">{course.description}</p>
        )}
        <div className="flex items-center gap-3 mt-1 text-xs text-[var(--tx7)]">
          {course.subject && <span>{course.subject}</span>}
          {course.grade   && <span>{course.grade}</span>}
          <span><BookOpen size={10} className="inline mr-0.5" />{course.units.length} units</span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-4 mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[var(--tx3)] text-sm font-medium">Your progress</span>
          <span className="text-purple-400 text-sm font-bold">{pct}%</span>
        </div>
        <div className="h-2 bg-[var(--ov2)] rounded-full overflow-hidden">
          <div className="h-full bg-purple-500 rounded-full transition-all"
            style={{ width: `${pct}%` }} />
        </div>
        <p className="text-[var(--tx8)] text-xs mt-1.5">
          {course.progress.visited} of {course.progress.total} concepts visited
        </p>
      </div>

      {/* Units accordion */}
      <div className="space-y-2">
        {course.units.map((unit, idx) => {
          const open       = expanded.has(unit.id);
          const unitVisited = unit.concepts.filter(c => c.visited).length;
          const unitTotal   = unit.concepts.length;

          return (
            <div key={unit.id}
              className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl overflow-hidden">
              <button
                onClick={() => toggleUnit(unit.id)}
                className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-[var(--ov1)] transition-colors">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="text-[var(--tx7)] text-xs font-mono shrink-0">
                    {String(idx + 1).padStart(2, '0')}
                  </span>
                  <div className="min-w-0">
                    <p className="text-[var(--tx1)] font-semibold truncate">{unit.title}</p>
                    <p className="text-[var(--tx7)] text-xs mt-0.5">
                      {unitVisited}/{unitTotal} done
                    </p>
                  </div>
                </div>
                {open
                  ? <ChevronDown size={16} className="text-[var(--tx7)] shrink-0" />
                  : <ChevronRight size={16} className="text-[var(--tx7)] shrink-0" />}
              </button>

              {open && (
                <div className="border-t border-[var(--bd)] divide-y divide-[var(--bd)]">
                  {unit.concepts.length === 0 ? (
                    <p className="px-5 py-4 text-[var(--tx7)] text-sm italic">No concepts yet</p>
                  ) : unit.concepts.map(concept => {
                    return (
                      <button key={concept.id}
                        onClick={() => openConcept(concept)}
                        className="w-full text-left flex items-start gap-3 px-5 py-3.5
                                   hover:bg-[var(--ov1)] transition-colors">
                        {concept.visited ? (
                          <CheckCircle2 size={16} className="text-green-400 shrink-0 mt-0.5" />
                        ) : (
                          <Circle size={16} className="text-[var(--tx8)] shrink-0 mt-0.5" />
                        )}
                        <div className="flex-1 min-w-0">
                          <p className={`text-sm font-medium ${concept.visited ? 'text-[var(--tx3)]' : 'text-[var(--tx1)]'}`}>
                            {concept.title}
                          </p>
                          {concept.description && (
                            <p className="text-[var(--tx7)] text-xs mt-0.5 line-clamp-1">
                              {concept.description}
                            </p>
                          )}
                          {concept.quiz_score !== undefined && concept.quiz_score !== null && (
                            <p className="text-xs text-amber-400 mt-0.5">
                              Quiz: {Math.round(concept.quiz_score)}%
                            </p>
                          )}
                        </div>
                        <Zap size={13} className="text-[var(--tx8)] shrink-0 mt-0.5" />
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
