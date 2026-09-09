const MAX_RUNGS = 6;

interface LadderWidgetProps {
  phase: 'idle' | 'climbing' | 'eureka';
  steps: number;
}

/** Geometric badge pictogram — same mark used in the app's version. */
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
 * Guided-discovery progress indicator for the genie side panel. This is a
 * deliberately different layout from the app's LadderWidget (a floating
 * vertical rail pinned to a wide desktop layout's spare right column) — a
 * ~380px side panel has no spare column, so a floating overlay there just
 * covers the message thread. This variant is a slim horizontal bar that
 * sits IN the document flow (no `fixed` positioning at all), so it can
 * never overlap content — same progress semantics as the app's version
 * (steps = turns taken, uncapped; MAX_RUNGS is only the bar's visual cap,
 * not a target), just laid out for a narrow column instead of a tall one.
 */
export function LadderWidget({ phase, steps }: LadderWidgetProps) {
  if (phase === 'idle') return null;

  const position = Math.min(Math.max(steps, 1), MAX_RUNGS);

  return (
    <div
      className="flex items-center gap-2.5 mx-4 mb-2 px-3 py-2 rounded-xl border border-[var(--bd)] bg-[var(--surface)]"
      title="Guided-discovery progress"
    >
      <div className="w-5 h-5 shrink-0">
        <ClimberMark eureka={phase === 'eureka'} />
      </div>

      <div className="flex-1 flex items-center gap-1">
        {Array.from({ length: MAX_RUNGS }, (_, i) => i + 1).map((rung) => (
          <div
            key={rung}
            className="h-1.5 flex-1 rounded-full transition-colors duration-300"
            style={{ background: rung <= position ? 'var(--indigo)' : 'var(--bd2)' }}
          />
        ))}
      </div>

      <span className="text-xs font-medium text-[var(--tx7)] whitespace-nowrap shrink-0">
        {phase === 'eureka' ? `Solved in ${steps}!` : `Step ${position}`}
      </span>
    </div>
  );
}
