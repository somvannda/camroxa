'use client';

import { LoaderCircle } from 'lucide-react';
import { useState } from 'react';

import { getGoogleAuthUrl } from '@/lib/auth-api';

const STORAGE_NEXT = 'camxora_google_next';
const STORAGE_STATE = 'camxora_google_state';

function redirectUri(): string {
  const configured = process.env.NEXT_PUBLIC_GOOGLE_REDIRECT_URI;
  if (configured) return configured;
  if (typeof window === 'undefined') return '';
  return `${window.location.origin}/auth/callback`;
}

export default function GoogleSignInButton({
  next = '/create',
  label = 'Continue with Google',
}: {
  next?: string;
  label?: string;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onClick() {
    setLoading(true);
    setError(null);
    try {
      const uri = redirectUri();
      const { url, state } = await getGoogleAuthUrl(uri);
      window.localStorage.setItem(STORAGE_NEXT, next);
      window.localStorage.setItem(STORAGE_STATE, state);
      window.location.assign(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Google sign-in unavailable');
      setLoading(false);
    }
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={onClick}
        disabled={loading}
        className="flex h-11 w-full items-center justify-center gap-3 rounded-xl border border-white/15 bg-white text-sm font-semibold text-slate-900 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? (
          <LoaderCircle className="h-4 w-4 animate-spin" />
        ) : (
          <svg className="h-4 w-4" viewBox="0 0 48 48" aria-hidden="true">
            <path
              fill="#EA4335"
              d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
            />
            <path
              fill="#4285F4"
              d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
            />
            <path
              fill="#FBBC05"
              d="M10.53 28.59A14.5 14.5 0 0 1 9.77 24c0-1.59.27-3.13.76-4.59l-7.98-6.19A23.94 23.94 0 0 0 0 24c0 3.86.92 7.51 2.56 10.78l7.97-6.19z"
            />
            <path
              fill="#34A853"
              d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.31-8.16 2.31-6.26 0-11.57-4.22-13.46-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
            />
          </svg>
        )}
        {loading ? 'Opening Google…' : label}
      </button>
      {error ? (
        <p className="rounded-lg border border-red-500/20 bg-red-500/10 p-2 text-xs text-red-300">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export { STORAGE_NEXT, STORAGE_STATE };
