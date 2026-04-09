'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useUserAuth } from '@/components/UserAuthContext';

export default function RootPage() {
  const { isAuthenticated, loading } = useUserAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (isAuthenticated) {
      router.replace('/chat');
    } else {
      router.replace('/landing');
    }
  }, [loading, isAuthenticated, router]);

  return null;
}
