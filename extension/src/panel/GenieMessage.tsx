import { MathText } from '../components/MathText';

export interface GenieMessageData {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

// Minimal reply renderer — markdown + math/chemistry formulas, matching the
// web app's chat window exactly via the shared MathText component (same
// preprocessMath()/KATEX_OPTIONS ported from frontend/lib/, same
// .ai-content prose rules ported into theme.css). No video chip, no quiz
// card, no next/navigation dependency: genie doesn't offer video
// generation, and quiz rendering has its own component.
export function GenieMessage({ message }: { message: GenieMessageData }) {
  const isUser = message.role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={
          isUser
            ? 'max-w-[85%] rounded-2xl px-3.5 py-2.5 bg-[var(--indigo)] text-white text-sm'
            : 'max-w-[92%] rounded-2xl px-3.5 py-2.5 bg-[var(--surface)] border border-[var(--bd)]'
        }
      >
        {isUser ? (
          <span className="text-sm">{message.content}</span>
        ) : (
          <div className="ai-content">
            <MathText>{message.content}</MathText>
          </div>
        )}
      </div>
    </div>
  );
}
