'use client';
import { useEffect, useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Loader, CheckCircle, XCircle } from 'lucide-react';
import { verifyMagicLink } from '@/lib/api';
import { useSessionStore } from '@/store/sessionStore';

function VerifyContent() {
  const searchParams = useSearchParams();
  const router       = useRouter();
  const { setUser }  = useSessionStore();

  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [error,  setError]  = useState('');

  useEffect(() => {
    const token = searchParams.get('token');
    if (!token) {
      setStatus('error');
      setError('No token found in the link. Please request a new one.');
      return;
    }

    verifyMagicLink(token)
      .then(data => {
        setUser(data.user, data.token);
        setStatus('success');
        setTimeout(() => router.replace('/'), 1500);
      })
      .catch(e => {
        setStatus('error');
        setError(e.message || 'This link has expired or already been used.');
      });
  }, []);

  return (
    <div className="min-h-screen bg-[#0f0f0f] flex items-center justify-center p-4">
      <div className="text-center max-w-sm">
        {status === 'loading' && (
          <>
            <Loader size={40} className="text-purple-400 animate-spin mx-auto mb-4" />
            <p className="text-white font-medium">Signing you in…</p>
            <p className="text-white/40 text-sm mt-1">Just a moment</p>
          </>
        )}

        {status === 'success' && (
          <>
            <CheckCircle size={40} className="text-green-400 mx-auto mb-4" />
            <p className="text-white font-semibold text-lg">You&apos;re in! 🎉</p>
            <p className="text-white/40 text-sm mt-1">Redirecting you now…</p>
          </>
        )}

        {status === 'error' && (
          <>
            <XCircle size={40} className="text-red-400 mx-auto mb-4" />
            <p className="text-white font-semibold mb-2">Sign-in failed</p>
            <p className="text-white/50 text-sm mb-6">{error}</p>
            <button
              onClick={() => router.push('/')}
              className="px-5 py-2.5 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-xl transition-colors"
            >
              Back to home
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export default function VerifyPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#0f0f0f] flex items-center justify-center">
        <Loader size={32} className="text-purple-400 animate-spin" />
      </div>
    }>
      <VerifyContent />
    </Suspense>
  );
}
