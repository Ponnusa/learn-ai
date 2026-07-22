'use client';
import { useRouter } from 'next/navigation';
import { Sidebar, MobileTopBar } from '@/components/layout/Sidebar';
import { AuthGuard } from '@/components/layout/AuthGuard';

export default function ClassroomsLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  return (
    <AuthGuard>
      <div className="flex h-screen overflow-hidden bg-[var(--bg)]">
        <Sidebar onNewChat={() => router.push('/')} />
        <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <MobileTopBar />
          <div className="flex-1 overflow-y-auto">
            {children}
          </div>
        </main>
      </div>
    </AuthGuard>
  );
}
