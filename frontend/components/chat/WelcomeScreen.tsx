'use client';
import { useMemo } from 'react';
import { useTranslation } from '@/hooks/useTranslation';

interface User {
  id: string;
  email: string;
  name?: string;
  tier: string;
}

interface Props {
  user: User | null;
  onSend: (text: string) => void;
}

/* ── Quotes — rotate daily (consistent for the whole day) ──────────────────── */
const QUOTES: { text: string; author: string }[] = [
  { text: 'The beautiful thing about learning is that no one can take it away from you.', author: 'B.B. King' },
  { text: 'Education is not the filling of a pail, but the lighting of a fire.', author: 'W.B. Yeats' },
  { text: 'An investment in knowledge pays the best interest.', author: 'Benjamin Franklin' },
  { text: 'The mind is not a vessel to be filled, but a fire to be kindled.', author: 'Plutarch' },
  { text: 'Live as if you were to die tomorrow. Learn as if you were to live forever.', author: 'Mahatma Gandhi' },
  { text: 'Imagination is more important than knowledge.', author: 'Albert Einstein' },
  { text: 'The more I learn, the more I realise how much I don\'t know.', author: 'Albert Einstein' },
  { text: 'In the middle of difficulty lies opportunity.', author: 'Albert Einstein' },
  { text: 'Science is a way of thinking much more than it is a body of knowledge.', author: 'Carl Sagan' },
  { text: 'Mathematics is the language in which the universe is written.', author: 'Galileo Galilei' },
  { text: 'Curiosity is the engine of achievement.', author: 'Ken Robinson' },
  { text: 'Tell me and I forget. Teach me and I remember. Involve me and I learn.', author: 'Benjamin Franklin' },
  { text: 'The science of today is the technology of tomorrow.', author: 'Edward Teller' },
  { text: 'It does not matter how slowly you go as long as you do not stop.', author: 'Confucius' },
  { text: 'Education is the passport to the future, for tomorrow belongs to those who prepare for it today.', author: 'Malcolm X' },
  { text: 'Knowledge is power.', author: 'Francis Bacon' },
  { text: 'The only way to do great work is to love what you do.', author: 'Steve Jobs' },
  { text: 'Somewhere, something incredible is waiting to be known.', author: 'Carl Sagan' },
  { text: 'Not all those who wander are lost.', author: 'J.R.R. Tolkien' },
  { text: 'The journey of a thousand miles begins with one step.', author: 'Lao Tzu' },
  { text: 'Every expert was once a beginner.', author: 'Helen Hayes' },
  { text: 'The roots of education are bitter, but the fruit is sweet.', author: 'Aristotle' },
  { text: 'You don\'t have to be great to start, but you have to start to be great.', author: 'Zig Ziglar' },
  { text: 'Push yourself, because no one else is going to do it for you.', author: 'Anonymous' },
  { text: 'The expert in anything was once a beginner.', author: 'Anonymous' },
  { text: 'Strive for progress, not perfection.', author: 'Anonymous' },
  { text: 'What we learn with pleasure, we never forget.', author: 'Alfred Mercier' },
  { text: 'The more you know, the more you realise you don\'t know.', author: 'Socrates' },
];

function getFirstName(user: User): string {
  if (user.name?.trim()) return user.name.trim().split(/\s+/)[0];
  const raw = user.email.split('@')[0].replace(/[._\-+]/g, ' ').trim().split(/\s+/)[0];
  return raw.charAt(0).toUpperCase() + raw.slice(1).toLowerCase();
}

export function WelcomeScreen({ user, onSend }: Props) {
  const { t } = useTranslation();

  const h = new Date().getHours();
  const greetText =
    h >= 5  && h < 12 ? t.chat.greetMorning :
    h >= 12 && h < 17 ? t.chat.greetAfternoon :
    h >= 17 && h < 21 ? t.chat.greetEvening :
    t.chat.greetNight;
  const emoji = h >= 5 && h < 12 ? '☀️' : h >= 12 && h < 17 ? '🌤️' : h >= 17 && h < 21 ? '🌆' : '🌙';

  // Same quote all day, changes at midnight
  const quote = useMemo(() => {
    const dayIndex = Math.floor(Date.now() / 86_400_000) % QUOTES.length;
    return QUOTES[dayIndex];
  }, []);

  // Pick 4 random-but-stable starter prompts for the day
  const prompts = useMemo(() => {
    const seed = Math.floor(Date.now() / 86_400_000);
    const shuffled = [...t.chat.starterPrompts].sort((a, b) =>
      Math.sin(seed + a.charCodeAt(0)) - Math.sin(seed + b.charCodeAt(0))
    );
    return shuffled.slice(0, 4);
  }, [t]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">

      {/* Logo */}
      <div className="mb-6">
        <img
          src="/learnx-logo.png"
          alt="LearnX-AI"
          className="h-36 sm:h-44 w-auto max-w-sm sm:max-w-md object-contain drop-shadow-lg"
        />
      </div>

      {/* Greeting */}
      {user ? (
        /* ── Logged-in greeting ──────────────────────────────── */
        <div className="mb-1">
          <h1 className="text-2xl md:text-3xl font-bold text-[var(--tx1)] leading-tight">
            {greetText}, {getFirstName(user)}! 👋
          </h1>
          <p className="text-[var(--tx6)] text-sm mt-2">
            {t.chat.welcomeReadyToLearn}
          </p>
        </div>
      ) : (
        /* ── Anonymous greeting ──────────────────────────────── */
        <div className="mb-1">
          <h1 className="text-2xl md:text-3xl font-bold text-[var(--tx1)] leading-tight">
            {greetText}! {emoji}
          </h1>
          <p className="text-[var(--tx6)] text-sm mt-2">
            {t.chat.welcomeTutorReady}
          </p>
        </div>
      )}

      {/* Daily quote */}
      <div className="mt-6 mb-8 max-w-md mx-auto">
        <div className="relative px-5 py-4 rounded-2xl bg-[var(--surface)] border border-[var(--bd)]">
          {/* Decorative quote mark */}
          <span className="absolute -top-3 left-4 text-3xl text-purple-500/30 font-serif leading-none select-none">
            "
          </span>
          <p className="text-[var(--tx4)] text-sm leading-relaxed italic">
            {quote.text}
          </p>
          <p className="text-[var(--tx8)] text-xs mt-2 font-medium not-italic">
            — {quote.author}
          </p>
        </div>
      </div>

      {/* Starter prompts */}
      <div data-tour="starter-prompts" className="flex flex-wrap gap-2 justify-center max-w-lg">
        {prompts.map((p, i) => (
          <button
            key={i}
            onClick={() => onSend(p)}
            className="px-4 py-2.5 rounded-xl text-sm transition-all
                       bg-[var(--surface)] hover:bg-[var(--ov4)]
                       border border-[var(--bd)] hover:border-[var(--bd2)]
                       text-[var(--tx3)] hover:text-[var(--tx1)]
                       shadow-sm"
          >
            {p}
          </button>
        ))}
      </div>

      <button
        onClick={() => window.dispatchEvent(new CustomEvent('start-home-tour'))}
        className="text-[11px] text-[var(--tx8)] hover:text-purple-400 transition-colors mt-1"
      >
        New here? Take a quick tour →
      </button>

    </div>
  );
}
