'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { FormEvent, Suspense, useCallback, useState } from 'react';
import { LoaderCircle, Shield } from 'lucide-react';

import AuthFormShell from '@/components/auth-form-shell';
import { useAuth } from '@/components/auth-provider';
import TurnstileWidget from '@/components/turnstile-widget';

function safeNextPath(raw: string | null): string {
  if (!raw) return '/create';
  if (!raw.startsWith('/') || raw.startsWith('//')) return '/';
  return raw;
}

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNextPath(params.get('next'));
  const { login } = useAuth();
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
      setError('Please complete the security check before signing in.');
      return;
    }

    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password, turnstileToken);
      router.replace(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed');
      setTurnstileToken('');
      setTurnstileKey((value) => value + 1);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthFormShell
      title="Welcome back"
      subtitle="Sign in to your CAMXORA Music account"
      footer={
        <p className="text-center text-sm text-slate-400">
          Don&apos;t have an account?{' '}
          <Link
            href={`/register?next=${encodeURIComponent(next)}`}
            className="font-medium text-purple-400 hover:text-purple-300"
          >
            Sign up
          </Link>
        </p>
      }
    >
      <form className="space-y-4" onSubmit={onSubmit}>
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
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            className="h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-white placeholder:text-slate-500 outline-none transition focus:border-purple-500/50"
          />
        </div>

        <div className="flex justify-center">
          <TurnstileWidget key={turnstileKey} action="login" onToken={handleTurnstileToken} />
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
          {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Shield className="h-4 w-4" />}
          Sign in
        </button>
      </form>
    </AuthFormShell>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[40vh] items-center justify-center text-slate-400">Loading…</div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
