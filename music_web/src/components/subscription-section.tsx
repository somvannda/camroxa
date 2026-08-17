'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Crown, Calendar, AlertCircle, Check, Loader2, X } from 'lucide-react';
import {
  fetchMySubscription,
  cancelSubscription,
  formatPrice,
  formatPlanDisplayName,
  creditsToSongs,
  type UserSubscription,
} from '@/lib/subscription-api';

export default function SubscriptionSection() {
  const [subscription, setSubscription] = useState<UserSubscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    loadSubscription();
  }, []);

  async function loadSubscription() {
    try {
      const data = await fetchMySubscription();
      setSubscription(data);
    } catch (err) {
      console.error('Failed to load subscription:', err);
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
    } catch (err: any) {
      console.error('Failed to cancel subscription:', err);
      alert(err.message || 'Failed to cancel subscription');
    } finally {
      setCancelling(false);
    }
  }

  if (loading) {
    return (
      <div className="rounded-3xl border border-white/8 bg-[rgba(8,10,20,0.55)] p-8 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-purple-400" />
      </div>
    );
  }

  // No active subscription - show upgrade CTA
  if (!subscription || subscription.status !== 'active') {
    return (
      <div className="rounded-3xl border border-purple-500/20 bg-gradient-to-br from-purple-900/20 via-[rgba(8,10,20,0.55)] to-transparent p-8 text-center">
        <div className="inline-flex p-3 rounded-full bg-purple-500/20 mb-4">
          <Crown className="w-8 h-8 text-purple-400" />
        </div>
        <h2 className="font-display text-2xl font-semibold text-white mb-2">
          Unlock Unlimited Music Creation
        </h2>
        <p className="text-slate-400 mb-6 max-w-md mx-auto">
          Subscribe to create AI-generated music with flexible credit-based plans.
          Choose monthly or yearly billing and save up to 15%.
        </p>
        <Link
          href="/pricing"
          className="inline-flex h-11 items-center rounded-xl bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 px-6 text-sm font-medium text-white transition-all"
        >
          View Plans & Pricing
        </Link>
      </div>
    );
  }

  // Active subscription
  const periodEnd = new Date(subscription.current_period_end);
  const daysLeft = Math.ceil((periodEnd.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
  const songs = creditsToSongs(subscription.monthly_credits_granted);

  return (
    <>
      <div className="rounded-3xl border border-purple-500/20 bg-gradient-to-br from-purple-900/20 via-[rgba(8,10,20,0.55)] to-transparent p-8">
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-full bg-gradient-to-br from-purple-500 to-pink-500">
              <Crown className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="font-display text-xl font-semibold text-white">
                {formatPlanDisplayName(subscription.plan_name)}
              </h2>
              <p className="text-xs text-slate-400 capitalize">
                {subscription.billing_cycle} subscription
              </p>
            </div>
          </div>
          {subscription.status === 'active' && (
            <span className="px-3 py-1 rounded-full bg-green-500/20 text-green-400 text-xs font-medium">
              Active
            </span>
          )}
        </div>

        {/* Subscription Info */}
        <div className="grid grid-cols-2 gap-4 mb-6 pb-6 border-b border-white/10">
          <div>
            <div className="text-sm text-slate-400 mb-1">Monthly Credits</div>
            <div className="text-2xl font-bold text-white">{songs} songs</div>
            <div className="text-xs text-slate-500">
              {subscription.monthly_credits_granted.toLocaleString()} credits
            </div>
          </div>
          <div>
            <div className="text-sm text-slate-400 mb-1">Next Billing</div>
            <div className="text-2xl font-bold text-white">{daysLeft}d</div>
            <div className="text-xs text-slate-500">
              {periodEnd.toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              })}
            </div>
          </div>
        </div>

        {/* Features */}
        <div className="mb-6">
          <div className="text-sm text-slate-400 mb-3">Includes:</div>
          <ul className="space-y-2">
            <li className="flex items-center gap-2 text-sm text-slate-300">
              <Check className="w-4 h-4 text-purple-400" />
              <span>{songs} AI-generated songs monthly</span>
            </li>
            <li className="flex items-center gap-2 text-sm text-slate-300">
              <Check className="w-4 h-4 text-purple-400" />
              <span>Full commercial rights</span>
            </li>
            <li className="flex items-center gap-2 text-sm text-slate-300">
              <Check className="w-4 h-4 text-purple-400" />
              <span>MP3 & WAV downloads</span>
            </li>
            <li className="flex items-center gap-2 text-sm text-slate-300">
              <Check className="w-4 h-4 text-purple-400" />
              <span>Buy additional credits anytime</span>
            </li>
          </ul>
        </div>

        {/* Cancel Warning */}
        {subscription.cancel_at_period_end && (
          <div className="mb-6 p-4 rounded-xl bg-yellow-500/10 border border-yellow-500/20 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
            <div className="text-sm">
              <div className="text-yellow-300 font-medium mb-1">Subscription ending soon</div>
              <div className="text-slate-400">
                Your subscription will be cancelled on{' '}
                {periodEnd.toLocaleDateString('en-US', {
                  month: 'long',
                  day: 'numeric',
                  year: 'numeric',
                })}
                . You'll keep access until then.
              </div>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-wrap gap-3">
          <Link
            href="/pricing"
            className="inline-flex h-10 items-center rounded-xl border border-purple-500/30 bg-purple-500/10 hover:bg-purple-500/20 px-4 text-sm text-purple-300 transition-all"
          >
            Change Plan
          </Link>
          {!subscription.cancel_at_period_end && (
            <button
              onClick={() => setShowCancelModal(true)}
              className="inline-flex h-10 items-center rounded-xl border border-white/10 px-4 text-sm text-slate-400 hover:text-white hover:bg-white/[0.04] transition-all"
            >
              Cancel Subscription
            </button>
          )}
        </div>
      </div>

      {/* Cancel Modal */}
      {showCancelModal && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={() => !cancelling && setShowCancelModal(false)}
        >
          <div
            className="bg-[#0c1230] rounded-2xl p-8 max-w-md w-full border border-purple-500/20"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-full bg-red-500/20">
                <AlertCircle className="w-5 h-5 text-red-400" />
              </div>
              <h3 className="text-2xl font-bold text-white">Cancel Subscription</h3>
            </div>

            <p className="text-slate-400 mb-6">
              Are you sure you want to cancel your subscription? You can choose to keep access
              until the end of your billing period or cancel immediately.
            </p>

            <div className="space-y-3">
              <button
                onClick={() => handleCancelSubscription(false)}
                disabled={cancelling}
                className="w-full py-3 rounded-xl bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {cancelling ? 'Processing...' : 'Cancel at Period End'}
              </button>
              <button
                onClick={() => handleCancelSubscription(true)}
                disabled={cancelling}
                className="w-full py-3 rounded-xl bg-red-500/20 hover:bg-red-500/30 text-red-300 font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {cancelling ? 'Processing...' : 'Cancel Immediately'}
              </button>
              <button
                onClick={() => setShowCancelModal(false)}
                disabled={cancelling}
                className="w-full py-3 rounded-xl border border-white/10 text-slate-400 hover:text-white hover:bg-white/[0.04] font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Keep Subscription
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
