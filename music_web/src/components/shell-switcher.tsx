'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';

import { useAuth } from '@/components/auth-provider';
import PlayerBar from '@/components/player-bar';
import Sidebar from '@/components/sidebar';
import SiteFooter from '@/components/site-footer';
import SiteHeader from '@/components/site-header';
import { isSandboxEnvironment } from '@/lib/site-urls';

function MarketingHeader() {
  const { user, loading } = useAuth();
  return (
    <>
      {isSandboxEnvironment() ? (
        <div className="border-b border-amber-400/25 bg-amber-500/10 px-4 py-2 text-center text-sm text-amber-100">
          Sandbox music portal — catalog and generation may use test media.
        </div>
      ) : null}
      <header className="sticky top-0 z-40 border-b border-white/8 bg-[rgba(5,8,18,0.82)] backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-3 md:px-6">
          <Link className="flex items-center gap-3" href="/">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img alt="Camxora" className="h-9 w-9" src="/camxora-logo.svg" />
            <div>
              <div className="font-display text-lg font-semibold tracking-[-0.05em] text-white">
                Camxora
              </div>
              <div className="text-[10px] uppercase tracking-[0.22em] text-fuchsia-100/58">Music</div>
            </div>
          </Link>
          <nav className="hidden items-center gap-6 text-sm text-slate-300 md:flex">
            <Link className="hover:text-white" href="/">
              Home
            </Link>
            <Link className="hover:text-white" href={user ? '/explore' : '/login?next=/explore'}>
              Explore
            </Link>
            <Link className="hover:text-white" href="/create">
              Create
            </Link>
          </nav>
          <div className="flex items-center gap-2">
            {loading ? (
              <div className="h-10 w-24 animate-pulse rounded-xl bg-white/5" />
            ) : user ? (
              <Link
                href="/create"
                className="inline-flex h-10 items-center rounded-xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-4 text-sm font-medium text-white"
              >
                Open app
              </Link>
            ) : (
              <>
                <Link
                  href="/login?next=/create"
                  className="hidden h-10 items-center rounded-xl border border-white/10 px-4 text-sm text-slate-100 sm:inline-flex"
                >
                  Log in
                </Link>
                <Link
                  href="/register?next=/create"
                  className="inline-flex h-10 items-center rounded-xl bg-white px-4 text-sm font-medium text-slate-950"
                >
                  Join Camxora
                </Link>
              </>
            )}
          </div>
        </div>
      </header>
    </>
  );
}

export default function ShellSwitcher({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const isAuthPage = pathname === '/login' || pathname === '/register';
  const showMarketing =
    !user &&
    (pathname === '/' || isAuthPage || pathname === '/explore' || pathname === '/create');

  if (showMarketing) {
    return (
      <div className="flex min-h-screen flex-col">
        <MarketingHeader />
        <main className="flex-1">{children}</main>
        {isAuthPage ? null : <SiteFooter />}
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col pb-32">
      <SiteHeader />
      <div className="mx-auto flex w-full max-w-[1600px] flex-1 gap-4 px-4 py-6 md:px-6">
        <Sidebar />
        <main className="min-w-0 flex-1">{children}</main>
      </div>
      <PlayerBar />
    </div>
  );
}
