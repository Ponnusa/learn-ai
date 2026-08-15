'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function SchoolAdminRoot() {
  const router = useRouter();
  useEffect(() => { router.replace('/school-admin/dashboard'); }, []);
  return null;
}
