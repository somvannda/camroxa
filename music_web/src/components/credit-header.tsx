'use client';

import { useState, useEffect } from 'react';
import { LogOut, Plus, Sparkles } from 'lucide-react';
import { fetchCreditBalance, type CreditBalance } from '@/lib/subscription-api';
import TopupModal from '@/components/topup-modal';
import PricingModal from '@/components/pricing-modal';
import { useAuth } from '@/components/auth-provider';
import { cn } from '@/lib/cn';

type CreditHeaderProps = {
  variant?: 'header' | 'compact' | 'sidebar';
};

type CreditDisplay = {
  used: number;
  limit: number;
  remaining: number;
  progressPct: number;
  resetLabel: string | null;
  promoText: string | null;
  isLow: boolean;
  hasSubscription: boolean;
};

function computeCreditDisplay(balance: CreditBalance | null): CreditDisplay {
  if (!balance) {
    return {
      used: 0,
      limit: 50,
      remaining: 0,
      progressPct: 0,
      resetLabel: 'Credit reset daily',
      promoText: 'Get more credits with Pro.',
      isLow: true,
      hasSubscription: false,
    };
  }

  if (balance.has_subscription) {
    const monthlyGranted = balance.monthly_credits + balance.monthly_credits_used;
    const limit = Math.max(monthlyGranted, 1);
    const used = balance.monthly_credits_used;
    return {
      used,
      limit,
      remaining: balance.total_credits,
      progressPct: Math.min(100, Math.round((used / limit) * 100)),
      resetLabel: null,
      promoText: null,
      isLow: balance.total_credits > 0 && balance.total_credits < 30,
      hasSubscription: true,
    };
  }

  const limit = Math.max(balance.daily_free_limit, 1);
  const used = balance.daily_free_used;
  const remaining = balance.daily_free_credits;

  return {
    used,
    limit,
    remaining,
    progressPct: Math.min(100, Math.round((used / limit) * 100)),
    resetLabel: 'Credit reset daily',
    promoText: 'Get more credits with Pro.',
    isLow: remaining > 0 && remaining < 30,
    hasSubscription: false,
  };
}

function CreditProgressCard({
  display,
  onUpgrade,
  onTopUp,
}: {
  display: CreditDisplay;
  onUpgrade: () => void;
  onTopUp: () => void;
}) {
  return (
    <div className="mt-3 space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <div className="text-sm text-slate-300">
          <span className="font-semibold text-white">{display.used.toLocaleString()}</span>
          <span className="text-slate-500"> / </span>
          <span>{display.limit.toLocaleString()} credits</span>
        </div>
        <span className="text-[11px] text-slate-500">{display.remaining.toLocaleString()} left</span>
      </div>

      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.08]">
        <div
          className={cn(
            'h-full rounded-full transition-all',
            display.isLow ? 'bg-amber-400' : 'bg-gradient-to-r from-violet-500 to-fuchsia-500',
          )}
          style={{ width: `${display.progressPct}%` }}
        />
      </div>

      {display.resetLabel ? (
        <p className="text-[11px] text-slate-500">{display.resetLabel}</p>
      ) : null}

      {display.promoText ? (
        <p className="text-[11px] text-slate-400">{display.promoText}</p>
      ) : null}

      {!display.hasSubscription ? (
        <button
          type="button"
          onClick={onUpgrade}
          className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-[7px] border border-white/10 bg-white/[0.04] text-sm font-medium text-white transition hover:border-violet-400/30 hover:bg-violet-500/10"
        >
          <Sparkles className="h-4 w-4 text-fuchsia-300" />
          Upgrade to Pro
        </button>
      ) : (
        <button
          type="button"
          onClick={onTopUp}
          className={cn(
            'inline-flex h-10 w-full items-center justify-center gap-2 rounded-[7px] text-sm font-medium transition',
            display.isLow
              ? 'border border-amber-400/20 bg-amber-500/10 text-amber-100 hover:bg-amber-500/15'
              : 'border border-white/10 bg-white/[0.04] text-violet-200 hover:border-violet-400/30 hover:bg-violet-500/10',
          )}
        >
          <Plus className="h-4 w-4" />
          Top up
        </button>
      )}
    </div>
  );
}

export default function CreditHeader({ variant = 'compact' }: CreditHeaderProps) {
  const { user, logout } = useAuth();
  const [balance, setBalance] = useState<CreditBalance | null>(null);
  const [loading, setLoading] = useState(true);
  const [showTopupModal, setShowTopupModal] = useState(false);
  const [showPricingModal, setShowPricingModal] = useState(false);

  useEffect(() => {
    void loadData();
    const interval = setInterval(() => void loadData(), 30000);
    return () => clearInterval(interval);
  }, []);

  async function loadData() {
    try {
      const creditData = await fetchCreditBalance().catch(() => null);
      setBalance(creditData);
    } finally {
      setLoading(false);
    }
  }

  const modals = (
    <>
      <TopupModal isOpen={showTopupModal} onClose={() => setShowTopupModal(false)} />
      <PricingModal isOpen={showPricingModal} onClose={() => setShowPricingModal(false)} />
    </>
  );

  if (loading) {
    if (variant === 'header') {
      return (
        <div className="hidden h-10 w-44 animate-pulse rounded-full bg-white/[0.05] lg:block" />
      );
    }
    if (variant === 'sidebar') {
      return <div className="h-28 animate-pulse rounded-[7px] bg-white/[0.04]" />;
    }
    return (
      <div className="flex items-center gap-2 rounded-[7px] border border-purple-500/20 bg-purple-500/10 px-3 py-1.5">
        <span className="text-xs text-slate-300">Loading credits...</span>
      </div>
    );
  }

  const display = computeCreditDisplay(balance);

  if (variant === 'sidebar') {
    return (
      <>
        <div className="rounded-[7px] border border-white/10 bg-white/[0.03] p-3">
          <div className="flex items-center justify-between gap-2">
            <div className="text-xs uppercase tracking-[0.14em] text-slate-500">Account</div>
            <button
              type="button"
              onClick={() => void logout()}
              className="inline-flex items-center gap-1 rounded-[7px] px-2 py-1 text-[11px] text-slate-400 transition hover:bg-white/[0.05] hover:text-white"
            >
              <LogOut className="h-3.5 w-3.5" />
              Sign out
            </button>
          </div>

          {user ? (
            <div className="mt-2 min-w-0">
              <div className="truncate text-sm font-medium text-white">{user.display_name}</div>
              <div className="truncate text-xs text-slate-400">{user.email}</div>
            </div>
          ) : null}

          <CreditProgressCard
            display={display}
            onUpgrade={() => setShowPricingModal(true)}
            onTopUp={() => setShowTopupModal(true)}
          />
        </div>
        {modals}
      </>
    );
  }

  if (variant === 'header') {
    return (
      <>
        <div
          className={cn(
            'hidden items-center gap-0 overflow-hidden rounded-full border lg:flex',
            display.isLow ? 'border-amber-400/25 bg-amber-500/[0.08]' : 'border-white/10 bg-white/[0.04]',
          )}
        >
          <div className="flex items-center gap-2.5 px-3.5 py-2">
            <div className="min-w-0 leading-tight">
              <div className={cn('text-sm font-semibold', display.isLow ? 'text-amber-100' : 'text-white')}>
                {display.used} / {display.limit} credits
              </div>
              {display.resetLabel ? (
                <div className="text-[11px] text-slate-400">{display.resetLabel}</div>
              ) : (
                <div className="text-[11px] text-slate-400">{display.remaining.toLocaleString()} remaining</div>
              )}
            </div>
          </div>

          {display.hasSubscription ? (
            <button
              type="button"
              onClick={() => setShowTopupModal(true)}
              className={cn(
                'flex h-full items-center gap-1 border-l px-3.5 py-2 text-xs font-medium transition',
                display.isLow
                  ? 'border-amber-400/20 bg-amber-500/10 text-amber-100 hover:bg-amber-500/15'
                  : 'border-white/10 bg-violet-500/10 text-violet-200 hover:bg-violet-500/15',
              )}
            >
              <Plus className="h-3.5 w-3.5" />
              Top up
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setShowPricingModal(true)}
              className="flex h-full items-center gap-1 border-l border-white/10 bg-violet-500/10 px-3.5 py-2 text-xs font-medium text-violet-200 transition hover:bg-violet-500/15"
            >
              <Sparkles className="h-3.5 w-3.5" />
              Upgrade to Pro
            </button>
          )}
        </div>

        <button
          type="button"
          onClick={() => (display.hasSubscription ? setShowTopupModal(true) : setShowPricingModal(true))}
          className={cn(
            'inline-flex h-10 w-10 items-center justify-center rounded-[7px] border lg:hidden',
            display.isLow
              ? 'border-amber-400/25 bg-amber-500/10 text-amber-200'
              : 'border-white/10 bg-white/[0.04] text-violet-200',
          )}
          aria-label={display.hasSubscription ? 'Top up credits' : 'Upgrade to Pro'}
        >
          {display.hasSubscription ? <Plus className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
        </button>

        {modals}
      </>
    );
  }

  return (
    <>
      <div
        className={cn(
          'flex items-center gap-2 rounded-[7px] border px-3 py-1.5 transition-all',
          display.isLow ? 'border-yellow-500/20 bg-yellow-500/10' : 'border-purple-500/20 bg-purple-500/10',
        )}
      >
        <div className="min-w-0">
          <div className={cn('text-sm font-medium leading-tight', display.isLow ? 'text-yellow-300' : 'text-white')}>
            {display.used} / {display.limit} credits
          </div>
          {display.resetLabel ? (
            <div className="text-[11px] text-slate-400">{display.resetLabel}</div>
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => (display.hasSubscription ? setShowTopupModal(true) : setShowPricingModal(true))}
          className={cn(
            'ml-auto shrink-0 rounded-[7px] px-2.5 py-1 text-xs font-medium flex items-center gap-1 transition-all',
            display.isLow
              ? 'bg-yellow-500/20 text-yellow-300 hover:bg-yellow-500/30'
              : 'bg-purple-500/20 text-purple-300 hover:bg-purple-500/30',
          )}
        >
          {display.hasSubscription ? (
            <>
              <Plus className="h-3.5 w-3.5" />
              <span>Top up</span>
            </>
          ) : (
            <>
              <Sparkles className="h-3.5 w-3.5" />
              <span>Upgrade to Pro</span>
            </>
          )}
        </button>
      </div>
      {modals}
    </>
  );
}
