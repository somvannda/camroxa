'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useRef, useState } from 'react';
import { LoaderCircle, ShieldAlert } from 'lucide-react';

import AuthFormShell from '@/components/auth-form-shell';
import { STORAGE_NEXT, STORAGE_REF, STORAGE_STATE } from '@/components/google-signin-button';
import { useAuth } from '@/components/auth-provider';
import { completeGoogleCallback, fetchMusicUser } from '@/lib/auth-api';
import { DEFAULT_POST_AUTH_PATH, safeNextPath } from '@/lib/auth-redirect';

function GoogleCallbackInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { refresh } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    async function finish() {
      const code = params.get('code');
      const state = params.get('state');
      const oauthError = params.get('error');

      if (oauthError) {
        setError(
          oauthError === 'access_denied'
            ? 'Google sign-in was cancelled. You can try again.'
            : `Google sign-in failed (${oauthError}).`,
        );
        return;
      }
      if (!code || !state) {
        setError('Google did not return a valid sign-in response. Please try again.');
        return;
      }

      const expectedState = window.localStorage.getItem(STORAGE_STATE);
      if (expectedState && expectedState !== state) {
        setError('The Google sign-in session could not be verified. Please try again.');
        return;
      }

      const rawNext = window.localStorage.getItem(STORAGE_NEXT);
      const next = safeNextPath(rawNext) || DEFAULT_POST_AUTH_PATH;
      const referralCode = window.localStorage.getItem(STORAGE_REF) || undefined;
      window.localStorage.removeItem(STORAGE_STATE);
      window.localStorage.removeItem(STORAGE_NEXT);

      try {
        await completeGoogleCallback({ code, state, referral_code: referralCode });
        window.localStorage.removeItem(STORAGE_REF);
        await refresh();
        const me = await fetchMusicUser();
        if (me && me.email_confirmed === false) {
          router.replace(
            `/verify-email?email=${encodeURIComponent(me.email)}&next=${encodeURIComponent(next)}`,
          );
          return;
        }
        router.replace(next);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Google sign-in failed');
      }
    }

    void finish();
  }, [params, refresh, router]);

  if (!error) {
    return (
      <div className="flex min-h-[40vh] flex-col items-center justify-center gap-4 text-slate-300">
        <LoaderCircle className="h-7 w-7 animate-spin text-purple-400" />
        <p className="text-sm">Signing you in with Google…</p>
      </div>
    );
  }

  return (
    <AuthFormShell title="Google sign-in" subtitle="We couldn’t finish signing you in.">
      <div className="space-y-4">
        <div className="flex items-start gap-3 rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-200">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
        <Link
          href="/login"
          className="flex h-11 w-full items-center justify-center rounded-xl bg-gradient-to-r from-purple-600 to-pink-600 text-sm font-medium text-white"
        >
          Back to sign in
        </Link>
      </div>
    </AuthFormShell>
  );
}

export default function GoogleCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[40vh] items-center justify-center text-slate-400">
          Loading…
        </div>
      }
    >
      <GoogleCallbackInner />
    </Suspense>
  );
}
