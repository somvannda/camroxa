'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FormEvent, useState } from 'react';
import { ArrowRight, Search } from 'lucide-react';

import { useAuth } from '@/components/auth-provider';
import { isSandboxEnvironment } from '@/lib/site-urls';

export default function SiteHeader() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [query, setQuery] = useState('');

  function onSearch(event: FormEvent) {
    event.preventDefault();
    const value = query.trim();
    if (!value) {
      router.push('/search');
      return;
    }
    router.push(`/search?q=${encodeURIComponent(value)}`);
  }

  return (
    <>
      {isSandboxEnvironment() ? (
        <div className="border-b border-amber-400/25 bg-amber-500/10 px-4 py-2 text-center text-sm text-amber-100">
          Sandbox music portal — catalog and playback may use test media.
        </div>
      ) : null}
      <header className="sticky top-0 z-40 border-b border-white/8 bg-[rgba(5,8,18,0.82)] backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-[1600px] items-center gap-4 px-4 py-3 md:px-6">
          <Link className="flex shrink-0 items-center gap-3" href="/">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img alt="Camxora" className="h-9 w-9" src="/camxora-logo.svg" />
            <div className="hidden sm:block">
              <div className="font-display text-lg font-semibold tracking-[-0.05em] text-white">
                Camxora
              </div>
              <div className="text-[10px] uppercase tracking-[0.22em] text-fuchsia-100/58">
                Music Streaming
              </div>
            </div>
          </Link>

          <form onSubmit={onSearch} className="relative mx-auto hidden w-full max-w-xl flex-1 md:block">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="What do you want to play?"
              className="h-11 w-full rounded-full border border-white/10 bg-white/[0.04] pl-10 pr-4 text-sm text-white outline-none ring-violet-400/40 placeholder:text-slate-400 focus:border-violet-400/40 focus:ring-2"
            />
          </form>

          <div className="ml-auto flex items-center gap-2">
            <Link
              href="/search"
              className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] text-slate-200 md:hidden"
              aria-label="Search"
            >
              <Search className="h-4 w-4" />
            </Link>
            {loading ? (
              <div className="h-10 w-24 animate-pulse rounded-xl bg-white/5" />
            ) : user ? (
              <>
                <Link
                  href="/profile"
                  className="hidden h-10 max-w-[10rem] items-center truncate rounded-xl border border-white/10 bg-white/[0.03] px-4 text-sm font-medium text-slate-100 sm:inline-flex"
                >
                  {user.display_name}
                </Link>
                <button
                  type="button"
                  onClick={() => void logout()}
                  className="inline-flex h-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] px-4 text-sm font-medium text-slate-100 transition hover:bg-white/[0.06]"
                >
                  Sign out
                </button>
              </>
            ) : (
              <>
                <Link
                  className="hidden h-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] px-4 text-sm font-medium text-slate-100 transition hover:bg-white/[0.06] sm:inline-flex"
                  href="/login"
                >
                  Sign in
                </Link>
                <Link
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-4 text-sm font-medium text-white shadow-[0_18px_44px_rgba(118,77,255,0.32)]"
                  href="/register"
                >
                  Sign up
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </>
            )}
          </div>
        </div>
      </header>
    </>
  );
}
