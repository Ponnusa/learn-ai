'use client';

const MAX_RUNGS = 6;
const RUNG_SPACING = 32; // px between rungs — independent of the rungs' own CSS gap,
                          // this is what actually places the climber via inline style

interface LadderWidgetProps {
  phase: 'idle' | 'climbing' | 'eureka';
  steps: number;
}

/** Geometric badge pictogram — same mark for both poses, just re-angled/tinted
 *  for eureka (mirrors the "arms up" summit pose from the design preview). */
function ClimberMark({ eureka }: { eureka: boolean }) {
  return (
    <svg viewBox="0 0 26 26" className="w-full h-full" style={{ overflow: 'visible' }}>
      {eureka ? (
        <>
          <circle cx="13" cy="5.5" r="3.2" fill="var(--amber)" />
          <path
            fill="var(--amber)"
            d="M13 9 L20 6 L21.4 8.6 L15.4 12 L18 22 L15 22.6 L13 15 L11 22.6 L8 22 L10.6 12 L4.6 8.6 L6 6 Z"
          />
        </>
      ) : (
        <>
          <circle cx="12.5" cy="5.5" r="3.2" fill="var(--indigo)" />
          <path
            fill="var(--indigo)"
            d="M12.5 9 L18.5 12 L17 14.4 L13.6 12.6 L14.6 24 L11.6 24 L11 16 L8 24 L5.4 23 L9.4 13.4 L6 12 L7.6 9.2 Z"
          />
        </>
      )}
    </svg>
  );
}

/**
 * Right-side "climbing the ladder" indicator for an active guided-discovery
 * chain. Deliberately simple: progress = turns taken in the current chain
 * (from the same WAITING marker that already drives the action-toolbar
 * hiding), not answer correctness — that would need a new, separate
 * self-reported signal, and the WAITING marker alone took several rounds to
 * get reliable. No fixed total either, since a chain's real length is
 * decided turn-by-turn, not known upfront: 6 rungs is just the widget's
 * visual cap, not a target — a chain can resolve in 2 steps or 12. The
 * climber holds near the top rung once it runs past MAX_RUNGS rather than
 * overflowing, but `steps` itself (used for the eureka caption below) is
 * never capped, so the actual count is always shown accurately.
 * Hidden entirely outside an active chain (idle = not rendered at all) and
 * on narrower screens, since the chat layout has no right rail otherwise.
 */
export function LadderWidget({ phase, steps }: LadderWidgetProps) {
  if (phase === 'idle') return null;

  const position = Math.min(Math.max(steps, 1), MAX_RUNGS);

  // Positioning differs from the app's copy: that one is a `hidden lg:flex`
  // overlay assuming a wide desktop layout with room for a right rail. The
  // side panel IS a narrow column with no such breakpoint to gate on — this
  // variant always shows, pinned to the panel's own corner.
  return (
    <div
      className="flex fixed right-3 bottom-24 z-40 flex-col items-center
                 gap-2 bg-[var(--surface)] border border-[var(--bd)] rounded-2xl px-3 py-3 shadow-lg"
      title="Guided-discovery progress"
    >
      <div className="text-xs font-medium text-[var(--tx8)] text-center leading-snug">
        {phase === 'eureka'
          ? <>🎉 Solved in<br />{steps} {steps === 1 ? 'step' : 'steps'}!</>
          : `Step ${position}`}
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
          className="absolute left-1/2 -translate-x-1/2 w-5 h-5 transition-all duration-500 ease-out"
          style={{ bottom: (position - 1) * RUNG_SPACING }}
        >
          <ClimberMark eureka={phase === 'eureka'} />
        </div>
      </div>
    </div>
  );
}
