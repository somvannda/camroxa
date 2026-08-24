'use client';

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { X, Check, Sparkles, Zap, Crown, Loader2, Gift } from 'lucide-react';
import { useRouter } from 'next/navigation';
import {
  fetchSubscriptionPlans,
  fetchMySubscription,
  calculateDiscount,
  formatPrice,
  formatPlanDisplayName,
  FREE_CARD_BULLETS,
  PUBLIC_CARD_BULLETS,
  creditsToSongs,
  type SubscriptionPlan,
} from '@/lib/subscription-api';
import CutluyCheckoutModal from '@/components/cutluy-checkout-modal';
import { useAuth } from '@/components/auth-provider';

type PricingModalProps = {
  isOpen: boolean;
  onClose: () => void;
  defaultBillingCycle?: 'monthly' | 'yearly';
};

const planIcons = {
  Free: Gift,
  Starter: Sparkles,
  Creator: Zap,
  Studio: Crown,
};

const planColors = {
  Free: 'from-slate-500 to-slate-600',
  Starter: 'from-blue-500 to-cyan-500',
  Creator: 'from-purple-500 to-pink-500',
  Studio: 'from-yellow-500 to-orange-500',
};

export default function PricingModal({ isOpen, onClose, defaultBillingCycle = 'monthly' }: PricingModalProps) {
  const router = useRouter();
  const { user } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasSubscription, setHasSubscription] = useState(false);
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>(defaultBillingCycle);
  const [purchasingPlan, setPurchasingPlan] = useState<string | null>(null);
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);
  const [checkoutQrString, setCheckoutQrString] = useState<string | null>(null);
  const [checkoutPaymentId, setCheckoutPaymentId] = useState<string | null>(null);
  const [checkoutPlan, setCheckoutPlan] = useState<{ name: string; price: string } | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (isOpen) {
      void loadPlans();
    }
  }, [isOpen]);

  async function loadPlans() {
    try {
      setLoading(true);
      const [data, subscription] = await Promise.all([
        fetchSubscriptionPlans(),
        user ? fetchMySubscription().catch(() => null) : Promise.resolve(null),
      ]);
      setPlans(data.plans.filter((plan) => plan.is_public && plan.price_cents !== 7900));
      setHasSubscription(Boolean(subscription && subscription.status === 'active'));
    } catch (err) {
      console.error('Failed to load plans:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handlePurchase(plan: SubscriptionPlan) {
    if (!user) {
      onClose();
      router.push(`/login?next=${encodeURIComponent('/profile')}`);
      return;
    }

    setPurchasingPlan(plan.id);
    try {
      const currentSub = await fetchMySubscription().catch(() => null);
      if (currentSub && currentSub.status === 'active') {
        alert('You already have an active subscription. Cancel it first to switch plans.');
        setPurchasingPlan(null);
        return;
      }

      const baseUrl = window.location.origin;
      const { purchaseSubscription } = await import('@/lib/subscription-api');
      const result = await purchaseSubscription({
        plan_id: String(plan.id),
        success_url: `${baseUrl}/create`,
        cancel_url: `${baseUrl}/create`,
      });

      if (result.checkout_url) {
        const displayName = formatPlanDisplayName(plan.name);
        setCheckoutPlan({
          name: displayName,
          price: `${formatPrice(plan.price_cents)}/${billingCycle === 'monthly' ? 'mo' : 'yr'}`,
        });
        setCheckoutPaymentId(result.payment_id);
        setCheckoutQrString(result.qr_string || null);
        setCheckoutUrl(result.checkout_url);
        onClose();
      }
    } catch (err) {
      console.error('Purchase failed:', err);
      alert(err instanceof Error ? err.message : 'Failed to start checkout');
      setPurchasingPlan(null);
    }
  }

  if (!mounted) return null;

  const filteredPlans = plans
    .filter((plan) => plan.billing_cycle === billingCycle)
    .filter((plan) => plan.price_cents > 0 && plan.price_cents !== 7900)
    .sort((a, b) => a.display_order - b.display_order);
  const freePlan = plans.find(
    (plan) =>
      plan.is_public &&
      plan.price_cents <= 0 &&
      plan.name.replace(/[_-]/g, " ").toLowerCase().includes("free"),
  );

  const modal = (
    <div
      className="fixed inset-0 z-[200] overflow-y-auto overscroll-contain bg-black/80 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="pricing-modal-title"
    >
      <div className="flex min-h-full items-start justify-center p-3 pb-[calc(var(--music-player-height)+var(--music-menu-clearance)+1rem)] pt-4 sm:items-center sm:p-4 sm:pb-8">
      <div
        className="relative my-0 w-full max-w-6xl rounded-3xl border border-white/10 bg-slate-900 shadow-2xl sm:my-4"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 z-10 rounded-full p-2 text-slate-400 transition-all hover:bg-white/10 hover:text-white"
          aria-label="Close"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="sticky top-0 z-10 border-b border-white/10 bg-slate-900/95 p-4 text-center backdrop-blur sm:p-8">
          <h2 id="pricing-modal-title" className="text-2xl font-bold text-white sm:text-3xl">
            Choose Your Plan
          </h2>
          <p className="mt-2 text-slate-400">Start creating amazing music with AI</p>

          <div className="mt-6 inline-flex items-center gap-2 rounded-full bg-white/5 p-1">
            <button
              type="button"
              onClick={() => setBillingCycle('monthly')}
              className={`rounded-full px-5 py-2 text-sm font-medium transition-all sm:px-6 ${
                billingCycle === 'monthly'
                  ? 'bg-purple-600 text-white shadow-lg'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Monthly
            </button>
            <button
              type="button"
              onClick={() => setBillingCycle('yearly')}
              className={`rounded-full px-5 py-2 text-sm font-medium transition-all sm:px-6 ${
                billingCycle === 'yearly'
                  ? 'bg-purple-600 text-white shadow-lg'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Yearly
              <span className="ml-2 rounded-full bg-green-500/20 px-2 py-0.5 text-xs text-green-400">
                Save 15%
              </span>
            </button>
          </div>
        </div>

        <div className="p-4 sm:p-8">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
            </div>
          ) : (
            <div className={`grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4 ${freePlan ? "xl:grid-cols-4" : "xl:grid-cols-3"}`}>
              {freePlan ? (
              <div className="relative flex min-w-0 flex-col rounded-2xl border border-white/10 bg-white/5 p-4 sm:p-6">
                <div className="relative z-10 flex items-center gap-3 border-b border-white/10 pb-4">
                  <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${planColors.Free}`}>
                    <Gift className="h-5 w-5 text-white" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xl font-bold leading-tight text-white sm:text-2xl">Free</p>
                  </div>
                </div>
                <div className="mt-4">
                  <div className="flex items-baseline gap-2">
                    <span className="text-4xl font-bold text-white">$0</span>
                    <span className="text-slate-400">/mo</span>
                  </div>
                </div>
                <div className="mt-4 rounded-lg bg-white/5 p-3">
                  <div className="text-sm text-slate-400">Daily Credits</div>
                  <div className="mt-1 text-2xl font-bold text-white">{freePlan.daily_credits || freePlan.monthly_credits || 0}</div>
                  <div className="text-xs text-slate-500">Credit reset daily</div>
                </div>
                <ul className="mt-6 flex-1 space-y-3">
                  {FREE_CARD_BULLETS.map((feature) => (
                    <li key={feature} className="flex items-start gap-2 text-sm text-slate-300">
                      <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-green-400" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  onClick={() => {
                    if (!user) {
                      onClose();
                      router.push('/register');
                      return;
                    }
                    onClose();
                  }}
                  disabled={Boolean(user && !hasSubscription)}
                  className="mt-6 flex h-12 w-full items-center justify-center rounded-xl bg-white/10 text-sm font-medium text-white transition-all hover:bg-white/20 disabled:cursor-default disabled:opacity-60"
                >
                  {!user ? 'Sign up free' : hasSubscription ? 'Included with paid plans' : 'Current plan'}
                </button>
              </div>
              ) : null}

              {/* Paid plans */}
              {filteredPlans.map((plan) => {
                const displayName = formatPlanDisplayName(plan.name);
                const Icon = planIcons[displayName as keyof typeof planIcons] || Sparkles;
                const colorClass = planColors[displayName as keyof typeof planColors] || 'from-purple-500 to-pink-500';
                const isPopular = displayName === 'Creator';
                const tierKey = plan.name.split('_')[0].split(' ')[0].toLowerCase();

                let discount: number | null = null;
                if (billingCycle === 'yearly') {
                  const monthlyPlan = plans.find(
                    (item) =>
                      item.name.toLowerCase().startsWith(tierKey) && item.billing_cycle === 'monthly',
                  );
                  if (monthlyPlan) {
                    discount = calculateDiscount(monthlyPlan.price_cents, plan.price_cents);
                  }
                }

                return (
                  <div
                    key={plan.id}
                    className={`relative flex min-w-0 flex-col rounded-2xl border p-4 transition-all sm:p-6 ${
                      isPopular
                        ? 'border-purple-500/50 bg-gradient-to-b from-purple-500/10 to-transparent pt-8'
                        : 'border-white/10 bg-white/5'
                    }`}
                  >
                    {isPopular ? (
                      <div className="absolute -top-3 left-1/2 z-20 -translate-x-1/2">
                        <span className="rounded-full bg-gradient-to-r from-purple-600 to-pink-600 px-4 py-1 text-xs font-bold text-white shadow-lg">
                          MOST POPULAR
                        </span>
                      </div>
                    ) : null}

                    <div className="relative z-10 flex items-center gap-3 border-b border-white/10 pb-4">
                      <div
                        className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${colorClass}`}
                      >
                        <Icon className="h-5 w-5 text-white" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-xl font-bold leading-tight text-white sm:text-2xl">{displayName}</p>
                      </div>
                    </div>

                    <div className="mt-4">
                      <div className="flex items-baseline gap-2">
                        <span className="text-4xl font-bold text-white">{formatPrice(plan.price_cents)}</span>
                        <span className="text-slate-400">/{billingCycle === 'monthly' ? 'mo' : 'yr'}</span>
                      </div>
                      {discount ? (
                        <div className="mt-1 text-sm text-green-400">Save {discount}% with yearly billing</div>
                      ) : null}
                    </div>

                    <div className="mt-4 rounded-lg bg-white/5 p-3">
                      <div className="text-sm text-slate-400">Monthly Credits</div>
                      <div className="mt-1 text-2xl font-bold text-white">
                        {plan.monthly_credits.toLocaleString()}
                      </div>
                      <div className="text-xs text-slate-500">~ {creditsToSongs(plan.monthly_credits)} songs/mo</div>
                    </div>

                    <ul className="mt-6 flex-1 space-y-3">
                      {PUBLIC_CARD_BULLETS.map((feature) => (
                        <li key={feature} className="flex items-start gap-2 text-sm text-slate-300">
                          <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-green-400" />
                          <span>{feature}</span>
                        </li>
                      ))}
                    </ul>

                    <button
                      type="button"
                      onClick={() => void handlePurchase(plan)}
                      disabled={purchasingPlan === plan.id}
                      className={`mt-6 flex h-12 w-full items-center justify-center gap-2 rounded-xl text-sm font-medium transition-all ${
                        isPopular
                          ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-lg shadow-purple-500/25 hover:shadow-purple-500/40'
                          : 'bg-white/10 text-white hover:bg-white/20'
                      } disabled:cursor-not-allowed disabled:opacity-50`}
                    >
                      {purchasingPlan === plan.id ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Processing...
                        </>
                      ) : (
                        `Get ${displayName}`
                      )}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="border-t border-white/10 p-4 text-center sm:p-6">
          <p className="text-sm text-slate-400">
            All paid plans include high-quality audio downloads and commercial usage rights.
          </p>
        </div>
      </div>
    </div>
    </div>
  );

  return (
    <>
      {isOpen ? createPortal(modal, document.body) : null}
      <CutluyCheckoutModal
        isOpen={Boolean(checkoutUrl)}
        checkoutUrl={checkoutUrl}
        qrString={checkoutQrString}
        paymentId={checkoutPaymentId}
        kind="subscription"
        planName={checkoutPlan?.name}
        planPrice={checkoutPlan?.price}
        onClose={() => {
          setCheckoutUrl(null);
          setCheckoutQrString(null);
          setCheckoutPaymentId(null);
          setCheckoutPlan(null);
          setPurchasingPlan(null);
        }}
      />
    </>
  );
}
