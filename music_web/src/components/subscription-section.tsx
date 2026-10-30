'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { AlertCircle, Check, Coins, Crown, Loader2 } from 'lucide-react';
import {
  cancelSubscription,
  creditsToSongs,
  fetchCreditBalance,
  fetchMySubscription,
  formatPlanDisplayName,
  parseBillingDate,
  type CreditBalance,
  type UserSubscription,
} from '@/lib/subscription-api';
import TopupModal from '@/components/topup-modal';

/**
 * Profile billing section — packs-only.
 *
 * Subscriptions are no longer sold, so there is no plan grid and no renewal
 * checkout here. Credit packs are bought through the shared top-up dialog. A
 * grandfathered subscriber still sees their own plan read-only, and can cancel
 * the term they already paid for.
 */
export default function SubscriptionSection() {
  const [subscription, setSubscription] = useState<UserSubscription | null>(null);
  const [balance, setBalance] = useState<CreditBalance | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [showTopupModal, setShowTopupModal] = useState(false);

  useEffect(() => {
    void loadData();
  }, []);

  async function loadData() {
    try {
      const [sub, credits] = await Promise.all([
        fetchMySubscription().catch(() => null),
        fetchCreditBalance().catch(() => null),
      ]);
      setSubscription(sub);
      setBalance(credits);
    } catch (err) {
      console.error('Failed to load credits:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleCancelSubscription(immediately: boolean) {
    setCancelling(true);
    try {
      const result = await cancelSubscription({
        cancel_at_period_end: !immediately,
      });

      if (result.success && result.subscription) {
        setSubscription(result.subscription);
        setShowCancelModal(false);
        alert(result.message);
      }
    } catch (err: unknown) {
      console.error('Failed to cancel subscription:', err);
      alert(err instanceof Error ? err.message : 'Failed to cancel subscription');
    } finally {
      setCancelling(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center rounded-3xl border border-white/8 bg-[rgba(8,10,20,0.55)] p-8">
        <Loader2 className="h-6 w-6 animate-spin text-purple-400" />
      </div>
    );
  }

  const isSubscribed =
    subscription?.status === 'active' || Boolean(balance?.has_subscription);
  const totalCredits = Math.max(0, balance?.total_credits ?? 0);
  const songs = creditsToSongs(totalCredits);

  const periodEnd =
    parseBillingDate(subscription?.current_period_end) ||
    parseBillingDate(balance?.pack_expires_at) ||
    parseBillingDate(balance?.current_period_end);
  const planTitle = subscription?.plan_name
    ? formatPlanDisplayName(subscription.plan_name)
    : balance?.is_pro
      ? 'Pro'
      : 'Free';

  return (
    <>
      <div className="space-y-6">
        <div className="rounded-3xl border border-purple-500/20 bg-gradient-to-br from-purple-900/20 via-[rgba(8,10,20,0.55)] to-transparent p-8">
          <div className="mb-6 flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="rounded-full bg-gradient-to-br from-purple-500 to-pink-500 p-2">
                <Coins className="h-5 w-5 text-white" />
              </div>
              <div>
                <h2 className="font-display text-xl font-semibold text-white">Credits</h2>
                <p className="text-xs text-slate-400">
                  {isSubscribed ? planTitle : 'Pay as you go'}
                </p>
              </div>
            </div>
            <span className="rounded-full bg-green-500/20 px-3 py-1 text-xs font-medium text-green-400">
              Active
            </span>
          </div>

          <div className="mb-6 grid grid-cols-2 gap-4 border-b border-white/10 pb-6">
            <div>
              <div className="mb-1 text-sm text-slate-400">Available Credits</div>
              <div className="text-2xl font-bold text-white">
                {totalCredits.toLocaleString()}
              </div>
              <div className="text-xs text-slate-500">≈ {songs.toLocaleString()} songs</div>
            </div>
            <div>
              <div className="mb-1 text-sm text-slate-400">Credits Expire</div>
              <div className="text-2xl font-bold text-white">
                {periodEnd ? '—' : '30 days'}
              </div>
              <div className="text-xs text-slate-500">
                {periodEnd
                  ? periodEnd.toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })
                  : 'after your last purchase'}
              </div>
            </div>
          </div>

          <div className="mb-6">
            <div className="mb-3 text-sm text-slate-400">How credits work:</div>
            <ul className="space-y-2">
              <li className="flex items-center gap-2 text-sm text-slate-300">
                <Check className="h-4 w-4 text-purple-400" />
                <span>Buy a pack any time — no subscription needed</span>
              </li>
              <li className="flex items-center gap-2 text-sm text-slate-300">
                <Check className="h-4 w-4 text-purple-400" />
                <span>Credits are valid for 30 days from your last purchase</span>
              </li>
              <li className="flex items-center gap-2 text-sm text-slate-300">
                <Check className="h-4 w-4 text-purple-400" />
                <span>Buying again resets the clock on your whole balance</span>
              </li>
            </ul>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setShowTopupModal(true)}
              className="inline-flex h-10 items-center rounded-xl bg-gradient-to-r from-purple-500 to-pink-500 px-5 text-sm font-medium text-white transition-all hover:from-purple-600 hover:to-pink-600"
            >
              Buy credits
            </button>
            <Link
              href="/pricing"
              className="inline-flex h-10 items-center rounded-xl border border-white/10 px-4 text-sm text-slate-300 transition-all hover:bg-white/[0.04] hover:text-white"
            >
              See packs
            </Link>
            {subscription && !subscription.cancel_at_period_end ? (
              <button
                type="button"
                onClick={() => setShowCancelModal(true)}
                className="inline-flex h-10 items-center rounded-xl border border-white/10 px-4 text-sm text-slate-400 transition-all hover:bg-white/[0.04] hover:text-white"
              >
                Cancel legacy subscription
              </button>
            ) : null}
          </div>
        </div>

        {subscription?.cancel_at_period_end && periodEnd ? (
          <div className="flex items-start gap-3 rounded-2xl border border-yellow-500/20 bg-yellow-500/10 p-5">
            <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-yellow-400" />
            <div className="text-sm">
              <div className="mb-1 font-medium text-yellow-300">Subscription ending soon</div>
              <div className="text-slate-400">
                Your legacy subscription is cancelled on{' '}
                {periodEnd.toLocaleDateString('en-US', {
                  month: 'long',
                  day: 'numeric',
                  year: 'numeric',
                })}
                . You keep access until then, then buy credits as you go.
              </div>
            </div>
          </div>
        ) : null}

        {!isSubscribed ? (
          <div className="rounded-3xl border border-purple-500/20 bg-gradient-to-br from-purple-900/20 via-[rgba(8,10,20,0.55)] to-transparent p-8 text-center">
            <div className="mb-4 inline-flex rounded-full bg-purple-500/20 p-3">
              <Crown className="h-8 w-8 text-purple-400" />
            </div>
            <h2 className="mb-2 font-display text-2xl font-semibold text-white">
              Pay Only for What You Use
            </h2>
            <p className="mx-auto mb-6 max-w-md text-slate-400">
              No subscription required. Buy a pack of credits whenever you need them, and they stay
              valid for 30 days from your purchase.
            </p>
            <button
              type="button"
              onClick={() => setShowTopupModal(true)}
              className="inline-flex h-11 items-center rounded-xl bg-gradient-to-r from-purple-500 to-pink-500 px-6 text-sm font-medium text-white transition-all hover:from-purple-600 hover:to-pink-600"
            >
              Buy credits
            </button>
          </div>
        ) : null}
      </div>

      {showCancelModal ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          onClick={() => !cancelling && setShowCancelModal(false)}
        >
          <div
            className="w-full max-w-md rounded-2xl border border-purple-500/20 bg-[#0c1230] p-8"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-4 flex items-center gap-3">
              <div className="rounded-full bg-red-500/20 p-2">
                <AlertCircle className="h-5 w-5 text-red-400" />
              </div>
              <h3 className="text-2xl font-bold text-white">Cancel Subscription</h3>
            </div>

            <p className="mb-6 text-slate-400">
              Subscriptions are no longer sold, but you can still end the term you already paid for.
              Keep access until the end of your billing period, or cancel now.
            </p>

            <div className="space-y-3">
              <button
                type="button"
                onClick={() => void handleCancelSubscription(false)}
                disabled={cancelling}
                className="w-full rounded-xl bg-purple-500/20 py-3 font-medium text-purple-300 transition-all hover:bg-purple-500/30 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {cancelling ? 'Processing...' : 'Cancel at Period End'}
              </button>
              <button
                type="button"
                onClick={() => void handleCancelSubscription(true)}
                disabled={cancelling}
                className="w-full rounded-xl bg-red-500/20 py-3 font-medium text-red-300 transition-all hover:bg-red-500/30 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {cancelling ? 'Processing...' : 'Cancel Immediately'}
              </button>
              <button
                type="button"
                onClick={() => setShowCancelModal(false)}
                disabled={cancelling}
                className="w-full rounded-xl border border-white/10 py-3 font-medium text-slate-400 transition-all hover:bg-white/[0.04] hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                Keep Subscription
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <TopupModal isOpen={showTopupModal} onClose={() => setShowTopupModal(false)} />
    </>
  );
}
