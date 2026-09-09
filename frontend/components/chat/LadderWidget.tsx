'use client';

const MAX_RUNGS = 6;
const RUNG_SPACING = 32; // px between rungs — independent of the rungs' own CSS gap,
                          // this is what actually places the climber via inline style

interface LadderWidgetProps {
  phase: 'idle' | 'climbing' | 'eureka';
  steps: number;
}

/**
 * Right-side "climbing the ladder" indicator for an active guided-discovery
 * chain. Deliberately simple: progress = turns taken in the current chain
 * (from the same WAITING marker that already drives the action-toolbar
 * hiding), not answer correctness — that would need a new, separate
 * self-reported signal, and the WAITING marker alone took several rounds to
 * get reliable. No fixed total either, since a chain's real length is
 * decided turn-by-turn, not known upfront — the climber just holds near the
 * top rung if a chain runs longer than MAX_RUNGS, rather than overflowing.
 * Hidden entirely outside an active chain (idle = not rendered at all) and
 * on narrower screens, since the chat layout has no right rail otherwise.
 */
export function LadderWidget({ phase, steps }: LadderWidgetProps) {
  if (phase === 'idle') return null;

  const position = Math.min(Math.max(steps, 1), MAX_RUNGS);

  return (
    <div
      className="hidden lg:flex fixed right-6 top-1/2 -translate-y-1/2 z-40 flex-col items-center
                 gap-2 bg-[var(--surface)] border border-[var(--bd)] rounded-2xl px-4 py-4 shadow-lg"
      title="Guided-discovery progress"
    >
      <div className="text-xs font-medium text-[var(--tx8)]">
        {phase === 'eureka' ? '🎉 Eureka!' : `Step ${position}`}
      </div>

      <div
        className="relative flex flex-col-reverse items-center border-x-2 border-[var(--bd2)] px-3"
        style={{ height: MAX_RUNGS * RUNG_SPACING }}
      >
        {Array.from({ length: MAX_RUNGS }, (_, i) => i + 1).map(rung => (
          <div
            key={rung}
            className="w-8 h-1 rounded-full bg-[var(--bd2)]"
            style={{ marginBottom: rung === MAX_RUNGS ? 0 : RUNG_SPACING - 4 }}
          />
        ))}

        <div
          className="absolute left-1/2 -translate-x-1/2 text-lg transition-all duration-500 ease-out"
          style={{ bottom: (position - 1) * RUNG_SPACING }}
        >
          {phase === 'eureka' ? '🎉' : '🧗'}
        </div>
      </div>
    </div>
  );
}
