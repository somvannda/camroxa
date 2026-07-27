'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { FormEvent, Suspense, useState } from 'react';

import { useAuth } from '@/components/auth-provider';

function safeNextPath(raw: string | null): string {
  if (!raw) return '/library';
  if (!raw.startsWith('/') || raw.startsWith('//')) return '/library';
  return raw;
}

function RegisterForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNextPath(params.get('next'));
  const { register } = useAuth();
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [invitationCode, setInvitationCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register({
        email: email.trim(),
        password,
        display_name: displayName.trim(),
        ...(invitationCode.trim() ? { invitation_code: invitationCode.trim() } : {}),
      });
      router.replace(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign up failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-md rounded-3xl border border-white/8 bg-[rgba(8,10,20,0.72)] p-8 backdrop-blur">
      <h1 className="font-display text-3xl font-semibold text-white">Join Camxora Music</h1>
      <p className="mt-2 text-sm text-slate-300/70">
        One Camxora account. After sign-up you stay here for listening, playlists, and your music
        profile.
      </p>
      <form className="mt-8 space-y-4" onSubmit={onSubmit}>
        <label className="block space-y-2 text-sm text-slate-200">
          <span>Display name</span>
          <input
            required
            minLength={2}
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="h-12 w-full rounded-xl border border-white/10 bg-white/[0.04] px-4 text-white outline-none focus:border-violet-400/50"
          />
        </label>
        <label className="block space-y-2 text-sm text-slate-200">
          <span>Email</span>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="h-12 w-full rounded-xl border border-white/10 bg-white/[0.04] px-4 text-white outline-none focus:border-violet-400/50"
          />
        </label>
        <label className="block space-y-2 text-sm text-slate-200">
          <span>Password</span>
          <input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="h-12 w-full rounded-xl border border-white/10 bg-white/[0.04] px-4 text-white outline-none focus:border-violet-400/50"
          />
        </label>
        <label className="block space-y-2 text-sm text-slate-200">
          <span>Invitation code (if required)</span>
          <input
            value={invitationCode}
            onChange={(e) => setInvitationCode(e.target.value)}
            className="h-12 w-full rounded-xl border border-white/10 bg-white/[0.04] px-4 text-white outline-none focus:border-violet-400/50"
          />
        </label>
        {error ? <p className="text-sm text-rose-300">{error}</p> : null}
        <button
          type="submit"
          disabled={busy}
          className="inline-flex h-12 w-full items-center justify-center rounded-xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 text-sm font-medium text-white disabled:opacity-60"
        >
          {busy ? 'Creating account…' : 'Create account'}
        </button>
      </form>
      <p className="mt-6 text-sm text-slate-300/70">
        Already have an account?{' '}
        <Link className="text-white underline-offset-4 hover:underline" href={`/login?next=${encodeURIComponent(next)}`}>
          Sign in
        </Link>
      </p>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<div className="text-slate-400">Loading…</div>}>
      <RegisterForm />
    </Suspense>
  );
}
