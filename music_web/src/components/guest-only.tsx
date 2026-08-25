'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, type ReactNode } from 'react';

import { useAuth } from '@/components/auth-provider';
import { destinationForSignedInUser, safeNextPath } from '@/lib/auth-redirect';

export default function GuestOnly({ children }: { children: ReactNode }) {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNextPath(params.get('next'));
  const { user, loading } = useAuth();
  const destination = destinationForSignedInUser(user, next);

  useEffect(() => {
    if (!destination) return;
    router.replace(destination);
  }, [destination, router]);

  if (loading || destination) {
    const label =
      user && user.email_confirmed === false ? 'Opening email verification…' : 'Opening Create…';
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-slate-400">
        {loading ? 'Loading…' : label}
      </div>
    );
  }

  return children;
}
