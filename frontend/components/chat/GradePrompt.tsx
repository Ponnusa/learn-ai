'use client';
import { useTranslation } from '@/hooks/useTranslation';
import { useGradeStore } from '@/store/gradeStore';

interface Props {
  onSelect: (grade: string | null) => void;
}

export function GradePrompt({ onSelect }: Props) {
  const { t } = useTranslation();
  const { setGrade } = useGradeStore();

  function pick(grade: string | null) {
    setGrade(grade);
    onSelect(grade);
  }

  return (
    <div className="mx-auto w-full max-w-2xl px-4 pb-3">
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <p className="mb-3 text-sm font-medium text-[var(--text-secondary)]">
          {t.profile.gradeQuestion}
        </p>
        <div className="flex flex-wrap gap-2">
          {t.grades.map((g) => (
            <button
              key={g}
              onClick={() => pick(g)}
              className="rounded-full border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] transition-colors hover:border-[var(--accent)] hover:text-[var(--accent)]"
            >
              {g}
            </button>
          ))}
          <button
            onClick={() => pick(null)}
            className="rounded-full border border-transparent px-3 py-1.5 text-xs text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
          >
            {t.skip}
          </button>
        </div>
      </div>
    </div>
  );
}
