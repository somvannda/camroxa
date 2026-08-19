'use client';

import Link from 'next/link';

import { useAuth } from '@/components/auth-provider';
import ProfilePageClient from '@/components/profile-page-client';

export default function ProfilePage() {
  const { user, loading } = useAuth();

  if (loading) {
    return <p className="text-slate-400">Loading profile…</p>;
  }

  if (!user) {
    return (
      <div className="rounded-3xl border border-white/8 bg-[rgba(8,10,20,0.55)] p-10">
        <h1 className="font-display text-3xl font-semibold text-white">Your account</h1>
        <p className="mt-3 text-slate-300/70">Sign in to manage your Camxora Music account.</p>
        <Link
          href="/login?next=/profile"
          className="mt-6 inline-flex h-11 items-center rounded-xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-5 text-sm font-medium text-white"
        >
          Sign in
        </Link>
      </div>
    );
  }

  return <ProfilePageClient />;
}
