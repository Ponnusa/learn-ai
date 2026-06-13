'use client';
import { useState } from 'react';
import { X, Loader } from 'lucide-react';
import { updateStudentProfile } from '@/lib/api';

const GRADES = [
  'Grade 6–8', 'Grade 9–10', 'Grade 11–12',
  'Undergrad Y1–2', 'Undergrad Y3–4', 'Graduate', 'Self-learner',
];

const GOALS = [
  'Ace my exams', 'University entrance', 'Deep understanding',
  'Career change', 'Curiosity / Hobby', 'Professional development',
];

const SUBJECTS = ['Mathematics', 'Physics', 'Chemistry'];

const LEVELS = ['Beginner', 'Intermediate', 'Advanced'] as const;

const LEVEL_STYLE: Record<string, string> = {
  Beginner:     'bg-orange-500/20 text-orange-400 border-orange-500/40',
  Intermediate: 'bg-blue-500/20 text-blue-400 border-blue-500/40',
  Advanced:     'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
};

interface Props {
  userId: string;
  token?: string;
  onComplete: () => void;
  onDismiss: () => void;
}

export function ProfileNudgeCard({ userId, token, onComplete, onDismiss }: Props) {
  const [step, setStep]           = useState(0);
  const [grade, setGrade]         = useState<string | null>(null);
  const [goal, setGoal]           = useState<string | null>(null);
  const [subjectConf, setSubjectConf] = useState<Record<string, string>>({});
  const [saving, setSaving]       = useState(false);

  async function save(patch: Parameters<typeof updateStudentProfile>[0]) {
    try { await updateStudentProfile(patch, token); } catch {}
  }

  async function selectGrade(g: string) {
    setGrade(g);
    await save({ user_id: userId, grade: g });
    setStep(1);
  }

  async function selectGoal(g: string) {
    setGoal(g);
    await save({ user_id: userId, goal: g });
    setStep(2);
  }

  function toggleLevel(subject: string, level: string) {
    setSubjectConf(prev =>
      prev[subject] === level ? { ...prev, [subject]: '' } : { ...prev, [subject]: level }
    );
  }

  async function finish() {
    setSaving(true);
    const filled = Object.fromEntries(Object.entries(subjectConf).filter(([, v]) => v));
    if (Object.keys(filled).length > 0) {
      await save({ user_id: userId, subject_confidence: filled });
    }
    setSaving(false);
    onComplete();
  }

  const STEPS = ['Grade', 'Goal', 'Subjects'];

  return (
    <div className="px-4 pb-2">
      <div className="rounded-2xl border border-purple-500/20 bg-[var(--surface)] p-4 shadow-sm">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2.5">
            <span className="text-[var(--tx2)] text-xs font-semibold">Personalise your experience</span>
            <div className="flex gap-1">
              {STEPS.map((_, i) => (
                <div key={i}
                  className={`h-1 w-5 rounded-full transition-colors ${
                    i < step ? 'bg-purple-500' : i === step ? 'bg-purple-400' : 'bg-[var(--ov3)]'
                  }`}
                />
              ))}
            </div>
          </div>
          <button onClick={onDismiss} className="text-[var(--tx6)] hover:text-[var(--tx2)] transition-colors p-0.5">
            <X size={13} />
          </button>
        </div>

        {/* Step 0 — Grade */}
        {step === 0 && (
          <div>
            <p className="text-[var(--tx4)] text-xs mb-2.5">What grade or level are you in?</p>
            <div className="flex flex-wrap gap-1.5">
              {GRADES.map(g => (
                <button key={g} onClick={() => selectGrade(g)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition-all
                    ${grade === g
                      ? 'bg-purple-600 text-white border-purple-500'
                      : 'bg-[var(--ov2)] text-[var(--tx4)] border-[var(--bd)] hover:border-purple-500/40 hover:text-purple-400'
                    }`}>
                  {g}
                </button>
              ))}
            </div>
            <button onClick={() => setStep(1)}
              className="mt-2 text-[10px] text-[var(--tx6)] hover:text-[var(--tx4)] transition-colors">
              Skip →
            </button>
          </div>
        )}

        {/* Step 1 — Goal */}
        {step === 1 && (
          <div>
            <p className="text-[var(--tx4)] text-xs mb-2.5">What is your main learning goal?</p>
            <div className="flex flex-wrap gap-1.5">
              {GOALS.map(g => (
                <button key={g} onClick={() => selectGoal(g)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition-all
                    ${goal === g
                      ? 'bg-indigo-600 text-white border-indigo-500'
                      : 'bg-[var(--ov2)] text-[var(--tx4)] border-[var(--bd)] hover:border-indigo-500/40 hover:text-indigo-400'
                    }`}>
                  {g}
                </button>
              ))}
            </div>
            <button onClick={() => setStep(2)}
              className="mt-2 text-[10px] text-[var(--tx6)] hover:text-[var(--tx4)] transition-colors">
              Skip →
            </button>
          </div>
        )}

        {/* Step 2 — Subject confidence */}
        {step === 2 && (
          <div>
            <p className="text-[var(--tx4)] text-xs mb-2.5">
              Rate your confidence by subject{' '}
              <span className="text-[var(--tx6)]">(optional — skip any you don't study)</span>
            </p>
            <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
              {SUBJECTS.map(subj => (
                <div key={subj} className="flex items-center gap-2">
                  <span className="text-[var(--tx4)] text-[11px] w-28 shrink-0">{subj}</span>
                  <div className="flex gap-1">
                    {LEVELS.map(lv => (
                      <button key={lv} onClick={() => toggleLevel(subj, lv)}
                        className={`px-2.5 py-1 rounded-lg text-[10px] font-medium border transition-all
                          ${subjectConf[subj] === lv
                            ? LEVEL_STYLE[lv]
                            : 'bg-[var(--ov2)] text-[var(--tx6)] border-[var(--bd)] hover:border-[var(--bd2)] hover:text-[var(--tx4)]'
                          }`}>
                        {lv}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex gap-2 mt-3">
              <button onClick={finish} disabled={saving}
                className="flex-1 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-50
                           text-white text-xs font-medium transition-colors flex items-center justify-center gap-1.5">
                {saving ? <><Loader size={11} className="animate-spin" /> Saving…</> : 'Save & personalise ✓'}
              </button>
              <button onClick={onComplete}
                className="px-3 py-2 rounded-xl text-[var(--tx6)] hover:text-[var(--tx2)] text-xs
                           border border-[var(--bd)] hover:border-[var(--bd2)] transition-all">
                Skip
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
