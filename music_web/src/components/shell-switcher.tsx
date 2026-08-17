'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import type { ReactNode } from 'react';
import { Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';

import { useAuth } from '@/components/auth-provider';
import PlayerBar from '@/components/player-bar';
import Sidebar from '@/components/sidebar';
import SiteFooter from '@/components/site-footer';
import SiteHeader from '@/components/site-header';
import PricingModal from '@/components/pricing-modal';

function MarketingHeader() {
  const { user, loading } = useAuth();
  const [showPricingModal, setShowPricingModal] = useState(false);
  return (
    <>
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
            <button
              onClick={() => setShowPricingModal(true)}
              className="flex items-center gap-1.5 hover:text-white"
            >
              <Sparkles className="h-3.5 w-3.5" />
              Pricing
            </button>
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
      <PricingModal isOpen={showPricingModal} onClose={() => setShowPricingModal(false)} />
    </>
  );
}

function LockedConfirmHeader() {
  const { logout } = useAuth();
  return (
    <header className="sticky top-0 z-40 border-b border-white/8 bg-[rgba(5,8,18,0.82)] backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-3 md:px-6">
        <div className="flex items-center gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img alt="Camxora" className="h-9 w-9" src="/camxora-logo.svg" />
          <div>
            <div className="font-display text-lg font-semibold tracking-[-0.05em] text-white">
              Camxora
            </div>
            <div className="text-[10px] uppercase tracking-[0.22em] text-fuchsia-100/58">Music</div>
          </div>
        </div>
        <button
          type="button"
          onClick={() => void logout()}
          className="h-10 rounded-xl border border-white/10 px-4 text-sm text-slate-100 hover:bg-white/5"
        >
          Sign out
        </button>
      </div>
    </header>
  );
}

export default function ShellSwitcher({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading } = useAuth();
  const needsConfirm = Boolean(user && user.email_confirmed === false);
  const isAuthPage =
    pathname === '/login' || pathname === '/register' || pathname === '/verify-email';
  const showMarketing =
    !loading &&
    !user &&
    (pathname === '/' || isAuthPage || pathname === '/explore' || pathname === '/create');

  useEffect(() => {
    if (loading || !needsConfirm || !user) return;
    if (pathname === '/verify-email') return;
    const next = pathname.startsWith('/') && !pathname.startsWith('//') ? pathname : '/create';
    router.replace(
      `/verify-email?email=${encodeURIComponent(user.email)}&next=${encodeURIComponent(next)}`,
    );
  }, [loading, needsConfirm, pathname, router, user]);

  if (needsConfirm) {
    return (
      <div className="flex min-h-screen flex-col">
        <LockedConfirmHeader />
        <main className="flex-1">{children}</main>
      </div>
    );
  }

  if (showMarketing) {
    return (
      <div className="flex min-h-screen flex-col">
        <MarketingHeader />
        <main className="flex-1">{children}</main>
        <SiteFooter />
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-slate-950">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <SiteHeader />
        <main className="music-scroll min-h-0 flex-1 overflow-y-auto px-4 py-6 pb-[calc(var(--music-player-height)+1.5rem)] md:px-6">{children}</main>
        <PlayerBar />
      </div>
    </div>
  );
}
