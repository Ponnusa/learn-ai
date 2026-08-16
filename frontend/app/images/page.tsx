'use client';
import { useEffect, Suspense } from 'react';
import { useRouter } from 'next/navigation';

function ImagesRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/assets?tab=diagrams');
  }, []);
  return null;
}

export default function ImagesPage() {
  return (
    <Suspense fallback={null}>
      <ImagesRedirect />
    </Suspense>
  );
}
