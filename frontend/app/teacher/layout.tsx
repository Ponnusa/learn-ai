'use client';
import { useRouter } from 'next/navigation';
import { Sidebar, MobileTopBar } from '@/components/layout/Sidebar';
import { AuthGuard } from '@/components/layout/AuthGuard';

const TEACHER_ROLES = ['teacher', 'institution_admin', 'super_admin'];

export default function TeacherLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  return (
    <AuthGuard requireRole={TEACHER_ROLES} loginPath="/auth/login">
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
