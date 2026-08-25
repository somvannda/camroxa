'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { FormEvent, Suspense, useCallback, useState } from 'react';
import { Check, LoaderCircle } from 'lucide-react';

import AuthFormShell from '@/components/auth-form-shell';
import { useAuth } from '@/components/auth-provider';
import GuestOnly from '@/components/guest-only';
import TurnstileWidget from '@/components/turnstile-widget';
import { safeNextPath } from '@/lib/auth-redirect';

function RegisterForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNextPath(params.get('next'));
  const { register } = useAuth();
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [turnstileToken, setTurnstileToken] = useState('');
  const [turnstileKey, setTurnstileKey] = useState(0);

  const handleTurnstileToken = useCallback((token: string) => {
    setTurnstileToken(token);
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!turnstileToken) {
      setError('Please complete the security check before signing up.');
      return;
    }

    setBusy(true);
    setError(null);
    try {
      await register({
        email: email.trim(),
        password,
        display_name: displayName.trim(),
        cf_turnstile_response: turnstileToken,
      });
      router.replace(
        `/verify-email?email=${encodeURIComponent(email.trim())}&next=${encodeURIComponent(next)}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign up failed');
      setTurnstileToken('');
      setTurnstileKey((value) => value + 1);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthFormShell
      title="Create your account"
      subtitle="Subscribe to a plan to get monthly credits for music generation."
      footer={
        <p className="text-center text-sm text-slate-400">
          Already have an account?{' '}
          <Link
            href={`/login?next=${encodeURIComponent(next)}`}
            className="font-medium text-purple-400 hover:text-purple-300"
          >
            Sign in
          </Link>
        </p>
      }
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-300">Display name</label>
          <input
            required
            minLength={2}
            maxLength={50}
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Your name"
            className="h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-white placeholder:text-slate-500 outline-none transition focus:border-purple-500/50"
          />
        </div>

        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-300">Email address</label>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-white placeholder:text-slate-500 outline-none transition focus:border-purple-500/50"
          />
        </div>

        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-300">Password</label>
          <input
            type="password"
            required
            minLength={8}
            maxLength={128}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            className="h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-white placeholder:text-slate-500 outline-none transition focus:border-purple-500/50"
          />
          <p className="text-xs text-slate-500">
            At least 8 characters with uppercase, lowercase, and a number.
          </p>
        </div>

        <div className="flex justify-center">
          <TurnstileWidget key={turnstileKey} action="register" onToken={handleTurnstileToken} />
        </div>

        {error ? (
          <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-300">
            {error}
          </div>
        ) : null}

        <button
          type="submit"
          disabled={busy || !turnstileToken}
          className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-pink-600 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
          Create account
        </button>

        <p className="text-center text-xs text-slate-500">
          By signing up, you agree to our Terms of Service and Privacy Policy.
        </p>
      </form>
    </AuthFormShell>
  );
}

export default function RegisterPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[40vh] items-center justify-center text-slate-400">Loading…</div>
      }
    >
      <GuestOnly>
        <RegisterForm />
      </GuestOnly>
    </Suspense>
  );
}
