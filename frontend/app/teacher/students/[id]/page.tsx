'use client';
import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  ArrowLeft, Loader2, CheckCircle2, Circle, Brain, MessageSquare, ChevronDown, ChevronUp,
  Sparkles, HelpCircle, Layers, Video, BookOpen, AlertTriangle,
} from 'lucide-react';
import { useSessionStore } from '@/store/sessionStore';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ConceptProgress { id: string; title: string; visited: boolean; quiz_score: number | null; }
interface CourseProgress  { id: string; name: string; concepts: ConceptProgress[]; }
interface StudentProgress { id: string; name: string; email: string; courses: CourseProgress[]; }

interface Profile {
  has_profile: boolean;
  skill_scores: Record<string, number>;
  known_misconceptions: string[];
  struggle_areas: string[];
  mastered_concepts: string[];
  grade: string | null;
  goal: string | null;
  avg_quiz_score: number | null;
  total_messages: number;
}

interface ConversationSummary {
  id: string; title: string; subject: string | null;
  message_count: number; last_message_at: string | null;
}
interface ChatMessage { role: string; content: string; created_at: string | null; }

interface Assignment {
  id: string; concept_id: string | null; kind: string; title: string; status: string; created_at: string | null;
}

const KIND_LABEL: Record<string, { label: string; icon: typeof HelpCircle }> = {
  quiz:       { label: 'Quiz',        icon: HelpCircle },
  flashcards: { label: 'Flashcards',  icon: Layers },
  video:      { label: 'Video',       icon: Video },
  studyset:   { label: 'Study set',   icon: BookOpen },
};

export default function TeacherStudentDetailPage() {
  const router    = useRouter();
  const params    = useParams();
  const studentId = params.id as string;
  const { user, token } = useSessionStore();

  const [data,          setData]          = useState<StudentProgress | null>(null);
  const [profile,       setProfile]       = useState<Profile | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading,       setLoading]       = useState(true);

  const [expandedConvId, setExpandedConvId] = useState<string | null>(null);
  const [convMessages,   setConvMessages]   = useState<ChatMessage[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);

  const [assignments,    setAssignments]    = useState<Assignment[]>([]);
  const [selectedConcept, setSelectedConcept] = useState('');
  const [assigning,      setAssigning]      = useState<string | null>(null);

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    if (!user) { router.replace('/auth/teacher'); return; }
    load();
  }, [user, studentId]);

  async function load() {
    setLoading(true);
    try {
      const [progressRes, profileRes, convRes, assignRes] = await Promise.all([
        fetch(`${API_BASE}/api/students/${studentId}/progress`, { headers }),
        fetch(`${API_BASE}/api/students/${studentId}/profile`, { headers }),
        fetch(`${API_BASE}/api/students/${studentId}/conversations`, { headers }),
        fetch(`${API_BASE}/api/assignments/student/${studentId}`, { headers }),
      ]);
      if (!progressRes.ok) { router.replace('/teacher/students'); return; }
      const progress = await progressRes.json();
      setData(progress);
      if (profileRes.ok) setProfile(await profileRes.json());
      if (convRes.ok)    setConversations(await convRes.json());
      if (assignRes.ok)  setAssignments(await assignRes.json());
      if (!selectedConcept) {
        const firstConcept = progress.courses?.[0]?.concepts?.[0]?.id;
        if (firstConcept) setSelectedConcept(firstConcept);
      }
    } finally { setLoading(false); }
  }

  async function assign(kind: string) {
    if (!selectedConcept) return;
    setAssigning(kind);
    try {
      const res = await fetch(`${API_BASE}/api/assignments`, {
        method: 'POST', headers,
        body: JSON.stringify({ student_id: studentId, concept_id: selectedConcept, kind }),
      });
      if (res.ok) {
        const assignRes = await fetch(`${API_BASE}/api/assignments/student/${studentId}`, { headers });
        if (assignRes.ok) setAssignments(await assignRes.json());
      }
    } finally { setAssigning(null); }
  }

  async function toggleConversation(convId: string) {
    if (expandedConvId === convId) { setExpandedConvId(null); return; }
    setExpandedConvId(convId);
    setLoadingMessages(true);
    try {
      const res = await fetch(`${API_BASE}/api/students/${studentId}/conversations/${convId}/messages`, { headers });
      setConvMessages(res.ok ? await res.json() : []);
    } finally { setLoadingMessages(false); }
  }

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader2 size={28} className="text-purple-400 animate-spin" />
    </div>
  );
  if (!data) return null;

  return (
    <div className="p-6 max-w-3xl mx-auto pb-16">
      <button onClick={() => router.push('/teacher/students')}
        className="flex items-center gap-1.5 text-[var(--tx7)] hover:text-[var(--purple)] text-sm mb-6 transition-colors">
        <ArrowLeft size={15} /> Back to students
      </button>

      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-[var(--tx1)] text-2xl font-bold mb-1">{data.name ?? data.email}</h1>
          <p className="text-[var(--tx7)] text-sm">{data.email}</p>
        </div>
        <button onClick={() => router.push(`/messages/${studentId}`)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-xl border border-[var(--bd)]
                     text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400 transition-all shrink-0">
          <MessageSquare size={14} /> Message
        </button>
      </div>

      {/* Learning profile */}
      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-4">
        <h2 className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <Brain size={12} /> Learning profile <span className="text-[var(--tx8)] font-normal">· from AI tutor sessions</span>
        </h2>
        {!profile?.has_profile ? (
          <p className="text-[var(--tx7)] text-sm">Not enough AI tutor activity yet to build a profile.</p>
        ) : (
          <div className="space-y-3">
            {Object.keys(profile.skill_scores).length > 0 && (
              <div className="space-y-1.5">
                {Object.entries(profile.skill_scores).map(([subject, score]) => (
                  <div key={subject} className="flex items-center gap-2 text-xs">
                    <span className="w-28 text-[var(--tx6)] truncate shrink-0">{subject}</span>
                    <div className="flex-1 h-1.5 rounded-full bg-[var(--ov3)] overflow-hidden">
                      <div className={`h-full rounded-full ${score >= 70 ? 'bg-green-500' : score >= 40 ? 'bg-amber-500' : 'bg-red-500'}`}
                        style={{ width: `${score}%` }} />
                    </div>
                    <span className="text-[var(--tx6)] w-8 text-right shrink-0">{Math.round(score)}</span>
                  </div>
                ))}
              </div>
            )}
            {profile.struggle_areas.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {profile.struggle_areas.map((a, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">{a}</span>
                ))}
              </div>
            )}
            {profile.known_misconceptions.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {profile.known_misconceptions.map((m, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20">{m}</span>
                ))}
              </div>
            )}
            <div className="flex items-center gap-3 text-xs text-[var(--tx7)]">
              {profile.grade && <span>Grade: {profile.grade}</span>}
              {profile.goal && <span>Goal: {profile.goal}</span>}
              <span>{profile.total_messages} AI tutor messages</span>
            </div>
          </div>
        )}
      </div>

      {/* Assign extra practice */}
      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-4">
        <h2 className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <Sparkles size={12} /> Assign extra practice
        </h2>

        {data.courses.length === 0 ? (
          <p className="text-[var(--tx7)] text-sm">No concepts available to assign yet.</p>
        ) : (
          <>
            <select value={selectedConcept} onChange={e => setSelectedConcept(e.target.value)}
              className="w-full bg-[var(--ov1)] border border-[var(--bd)] rounded-xl px-3 py-2 text-sm
                         text-[var(--tx1)] outline-none focus:border-purple-500/60 transition-colors mb-3">
              {data.courses.map(c => (
                <optgroup key={c.id} label={c.name}>
                  {c.concepts.map(concept => (
                    <option key={concept.id} value={concept.id}>{concept.title}</option>
                  ))}
                </optgroup>
              ))}
            </select>

            <div className="flex gap-2 flex-wrap">
              {Object.entries(KIND_LABEL).map(([kind, { label, icon: Icon }]) => (
                <button key={kind} onClick={() => assign(kind)} disabled={!!assigning}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-xl border border-[var(--bd)]
                             text-[var(--tx6)] hover:border-purple-500/40 hover:text-purple-400 transition-all disabled:opacity-50">
                  {assigning === kind ? <Loader2 size={14} className="animate-spin" /> : <Icon size={14} />}
                  {label}
                </button>
              ))}
            </div>
          </>
        )}

        {assignments.length > 0 && (
          <div className="mt-4 pt-4 border-t border-[var(--bd)] space-y-1.5">
            {assignments.map(a => {
              const meta = KIND_LABEL[a.kind];
              return (
                <div key={a.id} className="flex items-center gap-2 text-sm">
                  {meta && <meta.icon size={13} className="text-[var(--tx7)] shrink-0" />}
                  <span className="flex-1 text-[var(--tx2)] truncate">{a.title}</span>
                  {a.status === 'generating' && <span className="text-xs text-amber-400 flex items-center gap-1"><Loader2 size={11} className="animate-spin" /> Generating…</span>}
                  {a.status === 'ready'      && <span className="text-xs text-green-400">Ready</span>}
                  {a.status === 'failed'     && <span className="text-xs text-red-400 flex items-center gap-1"><AlertTriangle size={11} /> Failed</span>}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* AI tutor conversations (read-only) */}
      <div className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5 mb-4">
        <h2 className="text-[var(--tx2)] text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <MessageSquare size={12} /> AI Tutor Conversations
        </h2>
        {conversations.length === 0 ? (
          <p className="text-[var(--tx7)] text-sm">No AI tutor conversations yet.</p>
        ) : (
          <div className="space-y-2">
            {conversations.map(c => (
              <div key={c.id} className="border border-[var(--bd)] rounded-xl overflow-hidden">
                <button onClick={() => toggleConversation(c.id)}
                  className="w-full flex items-center justify-between gap-3 p-3 text-left hover:bg-[var(--ov1)] transition-colors">
                  <div className="min-w-0">
                    <p className="text-[var(--tx1)] text-sm font-medium truncate">{c.title || 'Untitled conversation'}</p>
                    <p className="text-[var(--tx7)] text-xs">
                      {c.subject && `${c.subject} · `}{c.message_count} messages
                      {c.last_message_at && ` · ${new Date(c.last_message_at).toLocaleDateString()}`}
                    </p>
                  </div>
                  {expandedConvId === c.id ? <ChevronUp size={14} className="text-[var(--tx7)] shrink-0" /> : <ChevronDown size={14} className="text-[var(--tx7)] shrink-0" />}
                </button>
                {expandedConvId === c.id && (
                  <div className="border-t border-[var(--bd)] p-3 space-y-2 max-h-80 overflow-y-auto bg-[var(--ov1)]">
                    {loadingMessages ? (
                      <Loader2 size={16} className="animate-spin text-[var(--tx7)] mx-auto" />
                    ) : convMessages.map((m, i) => (
                      <div key={i} className={`text-xs p-2 rounded-lg max-w-[85%] ${
                        m.role === 'user' ? 'bg-purple-500/10 text-[var(--tx2)] ml-auto' : 'bg-[var(--ov2)] text-[var(--tx2)]'
                      }`}>
                        {m.content}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Course progress */}
      {data.courses.length === 0 ? (
        <div className="bg-[var(--ov1)] border border-dashed border-[var(--bd)] rounded-2xl p-6 text-center">
          <p className="text-[var(--tx6)] text-sm">No courses assigned to this student's classrooms yet.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {data.courses.map(c => (
            <div key={c.id} className="bg-[var(--surface)] border border-[var(--bd)] rounded-2xl p-5">
              <h2 className="text-[var(--tx1)] font-semibold mb-3">{c.name}</h2>
              <div className="space-y-1.5">
                {c.concepts.map(concept => (
                  <div key={concept.id} className="flex items-center gap-3 text-sm py-1">
                    {concept.visited
                      ? <CheckCircle2 size={14} className="text-green-400 shrink-0" />
                      : <Circle size={14} className="text-[var(--tx8)] shrink-0" />}
                    <span className="flex-1 text-[var(--tx2)]">{concept.title}</span>
                    {concept.quiz_score !== null && (
                      <span className={
                        concept.quiz_score >= 70 ? 'text-green-400' : concept.quiz_score >= 40 ? 'text-amber-400' : 'text-red-400'
                      }>{Math.round(concept.quiz_score)}%</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
