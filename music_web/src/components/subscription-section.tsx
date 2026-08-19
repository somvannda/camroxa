'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { AlertCircle, Check, Crown, Loader2 } from 'lucide-react';
import {
  cancelSubscription,
  creditsToSongs,
  fetchCreditBalance,
  fetchMySubscription,
  fetchSubscriptionPlans,
  formatPlanDisplayName,
  formatPrice,
  matchCurrentPlan,
  parseBillingDate,
  purchaseSubscription,
  type CreditBalance,
  type SubscriptionPlan,
  type UserSubscription,
} from '@/lib/subscription-api';
import AvailablePlansGrid from '@/components/available-plans-grid';
import CutluyCheckoutModal from '@/components/cutluy-checkout-modal';
import { useAuth } from '@/components/auth-provider';

export default function SubscriptionSection() {
  const { user } = useAuth();
  const [subscription, setSubscription] = useState<UserSubscription | null>(null);
  const [balance, setBalance] = useState<CreditBalance | null>(null);
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly');
  const [purchasingPlanId, setPurchasingPlanId] = useState<string | null>(null);
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);
  const [checkoutPaymentId, setCheckoutPaymentId] = useState<string | null>(null);
  const [checkoutPlan, setCheckoutPlan] = useState<{ name: string; price: string } | null>(null);

  useEffect(() => {
    void loadSubscription();
  }, []);

  async function loadSubscription() {
    try {
      const [sub, credits, planData] = await Promise.all([
        fetchMySubscription().catch(() => null),
        fetchCreditBalance().catch(() => null),
        fetchSubscriptionPlans().catch(() => ({ plans: [] as SubscriptionPlan[] })),
      ]);
      setSubscription(sub);
      setBalance(credits);
      setPlans(planData.plans.filter((plan) => plan.is_public));
      if (sub?.billing_cycle === 'yearly' || sub?.billing_cycle === 'monthly') {
        setBillingCycle(sub.billing_cycle);
      }
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
    } catch (err: unknown) {
      console.error('Failed to cancel subscription:', err);
      alert(err instanceof Error ? err.message : 'Failed to cancel subscription');
    } finally {
      setCancelling(false);
    }
  }

  async function handleSelectPlan(plan: SubscriptionPlan) {
    if (!user) return;
    if (subscription?.status === 'active' && plan.id === subscription.plan_id) return;

    setPurchasingPlanId(plan.id);
    try {
      if (subscription?.status === 'active' && plan.id !== subscription.plan_id) {
        alert('Cancel your current plan first, then subscribe to a different plan.');
        setPurchasingPlanId(null);
        return;
      }
      const currentUrl = window.location.origin;
      const { checkout_url, payment_id } = await purchaseSubscription({
        plan_id: plan.id,
        success_url: `${currentUrl}/profile?payment=success`,
        cancel_url: `${currentUrl}/profile`,
      });
      setCheckoutPlan({
        name: formatPlanDisplayName(plan.name),
        price: formatPrice(plan.price_cents),
      });
      setCheckoutPaymentId(payment_id);
      setCheckoutUrl(checkout_url);
    } catch (err: unknown) {
      console.error('Purchase failed:', err);
      alert(err instanceof Error ? err.message : 'Failed to start checkout process');
      setPurchasingPlanId(null);
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
  const grantedCredits =
    subscription?.monthly_credits_granted ||
    (balance ? balance.monthly_credits + balance.monthly_credits_used : 0);
  const currentPlan = matchCurrentPlan(plans, subscription, grantedCredits);

  if (!isSubscribed) {
    return (
      <div className="rounded-3xl border border-purple-500/20 bg-gradient-to-br from-purple-900/20 via-[rgba(8,10,20,0.55)] to-transparent p-8 text-center">
        <div className="mb-4 inline-flex rounded-full bg-purple-500/20 p-3">
          <Crown className="h-8 w-8 text-purple-400" />
        </div>
        <h2 className="mb-2 font-display text-2xl font-semibold text-white">
          Unlock Unlimited Music Creation
        </h2>
        <p className="mx-auto mb-6 max-w-md text-slate-400">
          Subscribe to create AI-generated music with flexible credit-based plans. Choose monthly
          or yearly billing and save up to 15%.
        </p>
        <Link
          href="/pricing"
          className="inline-flex h-11 items-center rounded-xl bg-gradient-to-r from-purple-500 to-pink-500 px-6 text-sm font-medium text-white transition-all hover:from-purple-600 hover:to-pink-600"
        >
          View Plans & Pricing
        </Link>
      </div>
    );
  }

  const periodEnd =
    parseBillingDate(subscription?.current_period_end) ||
    parseBillingDate(balance?.current_period_end);
  const daysLeft = periodEnd
    ? Math.ceil((periodEnd.getTime() - Date.now()) / (1000 * 60 * 60 * 24))
    : null;
  const songs = creditsToSongs(grantedCredits);
  const planTitle = currentPlan
    ? formatPlanDisplayName(currentPlan.name)
    : subscription?.plan_name
      ? formatPlanDisplayName(subscription.plan_name)
      : 'Pro';

  return (
    <>
      <div className="space-y-6">
        <div className="rounded-3xl border border-purple-500/20 bg-gradient-to-br from-purple-900/20 via-[rgba(8,10,20,0.55)] to-transparent p-8">
          <div className="mb-6 flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="rounded-full bg-gradient-to-br from-purple-500 to-pink-500 p-2">
                <Crown className="h-5 w-5 text-white" />
              </div>
              <div>
                <h2 className="font-display text-xl font-semibold text-white">{planTitle}</h2>
                <p className="text-xs text-slate-400 capitalize">
                  {subscription?.billing_cycle || currentPlan?.billing_cycle || 'paid'} subscription
                </p>
              </div>
            </div>
            <span className="rounded-full bg-green-500/20 px-3 py-1 text-xs font-medium text-green-400">
              Active
            </span>
          </div>

          <div className="mb-6 grid grid-cols-2 gap-4 border-b border-white/10 pb-6">
            <div>
              <div className="mb-1 text-sm text-slate-400">Monthly Credits</div>
              <div className="text-2xl font-bold text-white">{songs} songs</div>
              <div className="text-xs text-slate-500">{grantedCredits.toLocaleString()} credits</div>
            </div>
            <div>
              <div className="mb-1 text-sm text-slate-400">Next Billing</div>
              <div className="text-2xl font-bold text-white">
                {daysLeft != null && Number.isFinite(daysLeft) ? `${Math.max(daysLeft, 0)}d` : '—'}
              </div>
              <div className="text-xs text-slate-500">
                {periodEnd
                  ? periodEnd.toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })
                  : 'Renews with your plan'}
              </div>
            </div>
          </div>

          <div className="mb-6">
            <div className="mb-3 text-sm text-slate-400">Includes:</div>
            <ul className="space-y-2">
              <li className="flex items-center gap-2 text-sm text-slate-300">
                <Check className="h-4 w-4 text-purple-400" />
                <span>{songs} AI-generated songs monthly</span>
              </li>
              <li className="flex items-center gap-2 text-sm text-slate-300">
                <Check className="h-4 w-4 text-purple-400" />
                <span>Full commercial rights</span>
              </li>
              <li className="flex items-center gap-2 text-sm text-slate-300">
                <Check className="h-4 w-4 text-purple-400" />
                <span>MP3 & WAV downloads</span>
              </li>
              <li className="flex items-center gap-2 text-sm text-slate-300">
                <Check className="h-4 w-4 text-purple-400" />
                <span>Buy additional credits anytime</span>
              </li>
            </ul>
          </div>

          {subscription?.cancel_at_period_end && periodEnd ? (
            <div className="mb-6 flex items-start gap-3 rounded-xl border border-yellow-500/20 bg-yellow-500/10 p-4">
              <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-yellow-400" />
              <div className="text-sm">
                <div className="mb-1 font-medium text-yellow-300">Subscription ending soon</div>
                <div className="text-slate-400">
                  Your subscription will be cancelled on{' '}
                  {periodEnd.toLocaleDateString('en-US', {
                    month: 'long',
                    day: 'numeric',
                    year: 'numeric',
                  })}
                  . You&apos;ll keep access until then.
                </div>
              </div>
            </div>
          ) : null}

          {subscription && !subscription.cancel_at_period_end ? (
            <button
              type="button"
              onClick={() => setShowCancelModal(true)}
              className="inline-flex h-10 items-center rounded-xl border border-white/10 px-4 text-sm text-slate-400 transition-all hover:bg-white/[0.04] hover:text-white"
            >
              Cancel Subscription
            </button>
          ) : null}
        </div>

        {plans.length ? (
          <AvailablePlansGrid
            plans={plans}
            billingCycle={billingCycle}
            onBillingCycleChange={setBillingCycle}
            currentPlanId={currentPlan?.id}
            purchasingPlanId={purchasingPlanId}
            onSelectPlan={(plan) => void handleSelectPlan(plan)}
          />
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
              Are you sure you want to cancel your subscription? You can choose to keep access
              until the end of your billing period or cancel immediately.
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

      <CutluyCheckoutModal
        isOpen={Boolean(checkoutUrl)}
        checkoutUrl={checkoutUrl}
        paymentId={checkoutPaymentId}
        kind="subscription"
        planName={checkoutPlan?.name}
        planPrice={checkoutPlan?.price}
        onClose={() => {
          setCheckoutUrl(null);
          setCheckoutPaymentId(null);
          setCheckoutPlan(null);
          setPurchasingPlanId(null);
        }}
      />
    </>
  );
}
