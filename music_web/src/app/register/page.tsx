'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import { ShieldCheck } from 'lucide-react';

import AuthFormShell from '@/components/auth-form-shell';
import GoogleSignInButton from '@/components/google-signin-button';
import GuestOnly from '@/components/guest-only';
import { safeNextPath } from '@/lib/auth-redirect';

function RegisterForm() {
  const params = useSearchParams();
  const next = safeNextPath(params.get('next'));

  return (
    <AuthFormShell
      title="Create your account"
      subtitle="Sign up with Google. Your email is verified automatically — no password to remember."
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
      <div className="space-y-5">
        <GoogleSignInButton next={next} label="Sign up with Google" />

        <div className="flex items-start gap-3 rounded-xl border border-white/10 bg-white/5 p-4 text-xs leading-relaxed text-slate-400">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
          <span>
            Google confirms your email address for us, so your account is ready immediately.
            Your Free plan includes 50 credits every month.
          </span>
        </div>

        <p className="text-center text-xs text-slate-500">
          Email and password sign-up is closed. Existing accounts can still sign in with a
          password. By continuing, you agree to our Terms of Service and Privacy Policy.
        </p>
      </div>
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
