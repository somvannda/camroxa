'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { FormEvent, Suspense, useEffect, useState } from 'react';
import { LoaderCircle, MailCheck } from 'lucide-react';

import AuthFormShell from '@/components/auth-form-shell';
import { useAuth } from '@/components/auth-provider';
import { fetchMusicUser, sendVerificationEmail, verifyEmailCode } from '@/lib/auth-api';
import { DEFAULT_POST_AUTH_PATH, safeNextPath } from '@/lib/auth-redirect';

function VerifyEmailForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNextPath(params.get('next'));
  const initialEmail = params.get('email') ?? '';
  const { refresh, user, loading } = useAuth();

  const [email, setEmail] = useState(initialEmail);
  const [code, setCode] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [resending, setResending] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (user?.email_confirmed) {
      router.replace(next);
    }
  }, [loading, next, router, user?.email_confirmed]);

  async function continueAfterVerify() {
    await refresh();
    const me = await fetchMusicUser();
    if (me?.email_confirmed) {
      router.replace(next);
      return;
    }
    router.replace(`/login?next=${encodeURIComponent(next || DEFAULT_POST_AUTH_PATH)}`);
  }

  async function onVerify(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await verifyEmailCode({ email: email.trim(), code: code.trim() });
      setMessage(result.message || 'Email verified successfully.');
      await continueAfterVerify();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed');
    } finally {
      setBusy(false);
    }
  }

  async function onResend() {
    setResending(true);
    setError(null);
    setMessage(null);
    try {
      const result = await sendVerificationEmail(email.trim());
      setMessage(result.message || 'Verification code sent.');
      if (result.is_verified) {
        await continueAfterVerify();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not resend code');
    } finally {
      setResending(false);
    }
  }

  if (loading || user?.email_confirmed) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-slate-400">
        {user?.email_confirmed ? 'Opening Create…' : 'Loading…'}
      </div>
    );
  }

  return (
    <AuthFormShell
      title="Verify your email"
      subtitle="Enter the 6-digit code we sent to your inbox."
      footer={
        <p className="text-center text-xs text-slate-500">
          Didn&apos;t get a code?{' '}
          <button
            type="button"
            onClick={onResend}
            disabled={resending || !email.trim()}
            className="font-medium text-purple-400 hover:text-purple-300 disabled:opacity-50"
          >
            {resending ? 'Sending…' : 'Resend code'}
          </button>
        </p>
      }
    >
      <form className="space-y-4" onSubmit={onVerify}>
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-300">Email address</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-white outline-none transition focus:border-purple-500/50"
          />
        </div>

        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-300">Verification code</label>
          <input
            inputMode="numeric"
            pattern="[0-9]{6}"
            maxLength={6}
            required
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            placeholder="123456"
            className="h-11 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-center text-lg tracking-[0.35em] text-white outline-none transition focus:border-purple-500/50"
          />
        </div>

        {message ? (
          <div className="rounded-lg border border-green-500/20 bg-green-500/10 p-3 text-sm text-green-300">
            {message}
          </div>
        ) : null}

        {error ? (
          <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-300">
            {error}
          </div>
        ) : null}

        <button
          type="submit"
          disabled={busy || code.length !== 6}
          className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-pink-600 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <MailCheck className="h-4 w-4" />}
          Verify email
        </button>
      </form>
    </AuthFormShell>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[40vh] items-center justify-center text-slate-400">Loading…</div>
      }
    >
      <VerifyEmailForm />
    </Suspense>
  );
}
