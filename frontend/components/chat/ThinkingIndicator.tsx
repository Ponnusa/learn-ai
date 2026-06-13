'use client';
import { useEffect, useState } from 'react';
import { useTranslation } from '@/hooks/useTranslation';

export function ThinkingIndicator() {
  const [phase, setPhase] = useState(0);
  const { t } = useTranslation();
  const PHASES = [t.chat.readingQuestion, t.chat.thinking, t.chat.crafting];

  useEffect(() => {
    const t = setInterval(() => setPhase(p => (p + 1) % PHASES.length), 2200);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="flex gap-3 mb-6 items-start">
      {/* Avatar with subtle pulse ring */}
      <div className="relative shrink-0 mt-0.5">
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-purple-500 to-blue-500
                        flex items-center justify-center text-white text-xs font-bold z-10 relative">
          AI
        </div>
        <span className="absolute inset-0 rounded-full bg-purple-500/30 animate-ping" />
      </div>

      {/* Thinking card */}
      <div className="flex items-center gap-3 bg-[var(--surface)] border border-[var(--bd)]
                      rounded-2xl rounded-tl-sm px-4 py-3 shadow-lg shadow-black/10">
        {/* Bouncing dots */}
        <div className="flex gap-1.5 items-center">
          {[0, 200, 400].map((delay, i) => (
            <span
              key={i}
              className="thinking-dot block w-2 h-2 rounded-full bg-purple-400"
              style={{ animationDelay: `${delay}ms` }}
            />
          ))}
        </div>

        {/* Phase label — fades between states */}
        <span
          key={phase}
          className="text-[var(--tx5)] text-sm"
          style={{ animation: 'fadeIn 0.4s ease' }}
        >
          {PHASES[phase]}
        </span>
      </div>
    </div>
  );
}
