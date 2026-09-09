import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

export interface GenieMessageData {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

// Minimal reply renderer — markdown + math only. No video chip, no quiz
// card, no next/navigation dependency: genie doesn't offer video generation
// (see plan), and quiz rendering is a later phase with its own component.
export function GenieMessage({ message }: { message: GenieMessageData }) {
  const isUser = message.role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={
          isUser
            ? 'max-w-[85%] rounded-2xl px-3.5 py-2.5 bg-[var(--indigo)] text-white text-sm'
            : 'max-w-[92%] rounded-2xl px-3.5 py-2.5 bg-[var(--surface)] border border-[var(--bd)] text-[var(--tx2)] text-sm leading-relaxed'
        }
      >
        {isUser ? (
          <span>{message.content}</span>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
            {message.content}
          </ReactMarkdown>
        )}
      </div>
    </div>
  );
}
