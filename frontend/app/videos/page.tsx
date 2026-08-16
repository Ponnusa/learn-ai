'use client';
import { useEffect, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';

function VideosRedirect() {
  const searchParams = useSearchParams();
  const router = useRouter();
  useEffect(() => {
    const id = searchParams.get('id');
    router.replace(id ? `/assets?id=${id}` : '/assets');
  }, []);
  return null;
}

export default function VideosPage() {
  return (
    <Suspense fallback={null}>
      <VideosRedirect />
    </Suspense>
  );
}
