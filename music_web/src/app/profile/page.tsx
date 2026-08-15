'use client';

import Link from 'next/link';

import { useAuth } from '@/components/auth-provider';

export default function ProfilePage() {
  const { user, loading, logout } = useAuth();

  if (loading) {
    return <p className="text-slate-400">Loading profile…</p>;
  }

  if (!user) {
    return (
      <div className="rounded-3xl border border-white/8 bg-[rgba(8,10,20,0.55)] p-10">
        <h1 className="font-display text-3xl font-semibold text-white">Music profile</h1>
        <p className="mt-3 text-slate-300/70">Sign in to view your Camxora Music profile.</p>
        <Link
          href="/login?next=/profile"
          className="mt-6 inline-flex h-11 items-center rounded-xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-5 text-sm font-medium text-white"
        >
          Sign in
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div className="rounded-3xl border border-white/8 bg-gradient-to-br from-violet-600/20 via-purple-900/10 to-transparent p-8">
        <p className="text-xs uppercase tracking-[0.2em] text-fuchsia-100/70">Listener profile</p>
        <h1 className="mt-2 font-display text-4xl font-semibold text-white">{user.display_name}</h1>
        <p className="mt-2 text-slate-300/75">{user.email}</p>
        <p className="mt-4 text-sm text-slate-300/60">
          This is your Camxora Music profile. Studio channel onboarding stays in the
          user portal if you later use the desktop app.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/library"
            className="inline-flex h-10 items-center rounded-xl border border-white/10 px-4 text-sm text-slate-100"
          >
            Your Library
          </Link>
          <button
            type="button"
            onClick={() => void logout()}
            className="inline-flex h-10 items-center rounded-xl border border-white/10 px-4 text-sm text-slate-100 hover:bg-white/[0.04]"
          >
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}
