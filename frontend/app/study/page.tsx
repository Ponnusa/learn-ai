'use client';
import { BookOpen, Plus, Search } from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { useRouter } from 'next/navigation';

export default function StudyPage() {
  const router = useRouter();
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar onNewChat={() => router.push('/')} />
      <main className="flex-1 flex flex-col items-center justify-center bg-[#0f0f0f] p-8">
        <div className="text-center max-w-md">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center mx-auto mb-6 shadow-lg shadow-indigo-500/20">
            <BookOpen size={28} className="text-white" />
          </div>
          <h1 className="text-white text-2xl font-bold mb-2">Study Sets</h1>
          <p className="text-white/40 text-sm mb-8">
            Save key concepts from your conversations into study sets.<br />
            Coming soon — keep chatting to build your library.
          </p>
          <button
            onClick={() => router.push('/')}
            className="flex items-center gap-2 mx-auto px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium transition-all"
          >
            <Plus size={15} /> Start a new chat
          </button>
        </div>
      </main>
    </div>
  );
}
