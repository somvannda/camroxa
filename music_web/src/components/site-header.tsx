'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FormEvent, useState } from 'react';
import { ArrowRight, Search, Sparkles } from 'lucide-react';

import { useAuth } from '@/components/auth-provider';
import CreditHeader from '@/components/credit-header';
import PricingModal from '@/components/pricing-modal';
import UserMenu from '@/components/user-menu';

export default function SiteHeader() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [query, setQuery] = useState('');
  const [showPricingModal, setShowPricingModal] = useState(false);

  function onSearch(event: FormEvent) {
    event.preventDefault();
    const value = query.trim();
    if (!value) {
      router.push('/explore');
      return;
    }
    router.push(`/explore?q=${encodeURIComponent(value)}`);
  }

  return (
    <>
      <header className="sticky top-0 z-40 h-16 shrink-0 border-b border-white/8 bg-[rgba(5,8,18,0.82)] backdrop-blur-xl">
        <div className="mx-auto flex h-full w-full max-w-[1600px] items-center gap-3 px-4 md:gap-4 md:px-6">
          <form onSubmit={onSearch} className="relative hidden w-full max-w-xl flex-1 md:block">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="What do you want to play?"
              className="h-11 w-full rounded-full border border-white/10 bg-white/[0.04] pl-10 pr-4 text-sm text-white outline-none ring-violet-400/40 placeholder:text-slate-400 focus:border-violet-400/40 focus:ring-2"
            />
          </form>

          <div className="ml-auto flex shrink-0 items-center gap-2">
            {!user ? (
              <button
                type="button"
                onClick={() => setShowPricingModal(true)}
                className="hidden h-10 items-center justify-center gap-2 rounded-xl border border-purple-500/30 bg-purple-500/10 px-4 text-sm font-medium text-purple-300 transition hover:bg-purple-500/20 lg:inline-flex"
              >
                <Sparkles className="h-4 w-4" />
                Pricing
              </button>
            ) : (
              <CreditHeader variant="header" />
            )}

            {loading ? (
              <div className="h-10 w-24 animate-pulse rounded-xl bg-white/5" />
            ) : user ? (
              <UserMenu />
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

      <PricingModal isOpen={showPricingModal} onClose={() => setShowPricingModal(false)} />
    </>
  );
}
