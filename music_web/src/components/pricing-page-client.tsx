'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Check, Sparkles, Zap, Crown, Gem, Loader2, Gift } from 'lucide-react';
import {
  fetchSubscriptionPlans,
  purchaseSubscription,
  formatPrice,
  formatPlanDisplayName,
  calculateDiscount,
  cardBulletsForPlan,
  creditCaptionLines,
  creditHeadlineNumber,
  type SubscriptionPlan,
} from '@/lib/subscription-api';
import CutluyCheckoutModal from '@/components/cutluy-checkout-modal';
import { useAuth } from '@/components/auth-provider';

export default function PricingPageClient() {
  const router = useRouter();
  const { user } = useAuth();
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly');
  const [purchasingPlanId, setPurchasingPlanId] = useState<string | null>(null);
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);
  const [checkoutQrString, setCheckoutQrString] = useState<string | null>(null);
  const [checkoutPaymentId, setCheckoutPaymentId] = useState<string | null>(null);
  const [checkoutPlan, setCheckoutPlan] = useState<{ name: string; price: string } | null>(null);

  useEffect(() => {
    loadPlans();
  }, []);

  async function loadPlans() {
    try {
      const { plans: allPlans } = await fetchSubscriptionPlans();
      setPlans(allPlans.filter((p) => p.is_public && p.price_cents !== 7900));
    } catch (err) {
      console.error('Failed to load plans:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleSelectPlan(plan: SubscriptionPlan) {
    if (!user) {
      router.push(`/login?next=/pricing`);
      return;
    }

    setPurchasingPlanId(plan.id);

    try {
      const currentUrl = window.location.origin;
      const { checkout_url, payment_id, qr_string } = await purchaseSubscription({
        plan_id: plan.id,
        success_url: `${currentUrl}/create`,
        cancel_url: `${currentUrl}/create`,
      });

      setCheckoutPlan({
        name: formatPlanDisplayName(plan.name),
        price: formatPrice(plan.price_cents),
      });
      setCheckoutPaymentId(payment_id);
      setCheckoutQrString(qr_string || null);
      setCheckoutUrl(checkout_url);
    } catch (err: any) {
      console.error('Purchase failed:', err);
      alert(err.message || 'Failed to start checkout process');
      setPurchasingPlanId(null);
    }
  }

  // Group plans by tier
  const monthlyPlans = plans.filter((p) => p.billing_cycle === 'monthly');
  const yearlyPlans = plans.filter((p) => p.billing_cycle === 'yearly');

  const displayPlans = billingCycle === 'monthly' ? monthlyPlans : yearlyPlans;

  // Sort by price
  const sortedPlans = [...displayPlans]
    .filter((plan) => plan.price_cents > 0)
    .sort((a, b) => a.price_cents - b.price_cents);
  const freePlan = plans.find(
    (plan) =>
      plan.is_public &&
      plan.price_cents <= 0 &&
      plan.name.replace(/[_-]/g, " ").toLowerCase().includes("free"),
  );

  // Calculate yearly discount from the first paid tier (Free has price 0).
  const paidMonthly = monthlyPlans.filter((plan) => plan.price_cents > 0);
  const paidYearly = yearlyPlans.filter((plan) => plan.price_cents > 0);
  const yearlyDiscount = paidMonthly[0] && paidYearly[0]
    ? calculateDiscount(paidMonthly[0].price_cents, paidYearly[0].price_cents)
    : 15;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-b from-[#0a0e27] to-[#1a1f3a]">
        <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
      </div>
    );
  }

  return (
    <>
    <div className="min-h-screen bg-gradient-to-b from-[#0a0e27] to-[#1a1f3a] text-white">
      {/* Header */}
      <div className="container mx-auto px-4 py-16 text-center">
        <h1 className="text-5xl font-display font-bold mb-4 bg-gradient-to-r from-purple-400 via-pink-400 to-purple-600 bg-clip-text text-transparent">
          Choose Your Plan
        </h1>
        <p className="text-xl text-gray-300 mb-8 max-w-2xl mx-auto">
          Create unlimited AI-generated music with flexible credit-based pricing
        </p>

        {/* Billing Toggle */}
        <div className="inline-flex items-center gap-3 bg-[#0c1230] rounded-full p-1 border border-purple-500/20">
          <button
            onClick={() => setBillingCycle('monthly')}
            className={`px-6 py-2 rounded-full transition-all ${
              billingCycle === 'monthly'
                ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white font-medium'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            Monthly
          </button>
          <button
            onClick={() => setBillingCycle('yearly')}
            className={`px-6 py-2 rounded-full transition-all flex items-center gap-2 ${
              billingCycle === 'yearly'
                ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white font-medium'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            Yearly
            <span className="text-xs bg-green-500 text-white px-2 py-0.5 rounded-full">
              Save {yearlyDiscount}%
            </span>
          </button>
        </div>
      </div>

      {/* Plans */}
      <div className="container mx-auto px-4 pb-20">
        <div className={`grid max-w-7xl grid-cols-1 gap-4 mx-auto md:grid-cols-2 lg:grid-cols-3 lg:gap-5 ${freePlan ? "xl:grid-cols-5" : "xl:grid-cols-4"}`}>
          {freePlan ? (
          <div className="relative rounded-2xl border-2 border-purple-500/20 bg-[#0c1230] p-5 md:p-6">
            <div className="mb-4 flex justify-center">
              <div className="rounded-full bg-purple-500/20 p-3">
                <Gift className="h-6 w-6 text-purple-400" />
              </div>
            </div>
            <h3 className="mb-2 text-center font-display text-xl font-bold">Free</h3>
            <div className="mb-6 text-center">
              <div className="flex items-baseline justify-center gap-1">
                <span className="text-3xl font-bold">$0</span>
                <span className="text-gray-400">/month</span>
              </div>
            </div>
            <div className="mb-6 border-b border-purple-500/20 pb-6 text-center">
              <div className="text-2xl font-bold text-purple-400">
                {creditHeadlineNumber(freePlan).toLocaleString()}
              </div>
              {creditCaptionLines(freePlan).map((line, index) => (
                <div
                  key={`${line}-${index}`}
                  className={index === 0 ? "text-sm text-gray-400" : "mt-1 text-xs text-gray-500"}
                >
                  {line}
                </div>
              ))}
            </div>
            <ul className="mb-8 space-y-3">
              {cardBulletsForPlan(freePlan).map((feature) => (
                  <li key={feature} className="flex items-start gap-3">
                    <Check className="mt-0.5 h-5 w-5 flex-shrink-0 text-purple-400" />
                    <span className="text-sm text-gray-300">{feature}</span>
                  </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={() => {
                if (!user) {
                  router.push('/register');
                  return;
                }
                router.push('/create');
              }}
              className="w-full rounded-lg border border-purple-500/30 bg-purple-500/20 py-3 font-medium text-purple-300 transition-all hover:bg-purple-500/30"
            >
              {user ? 'Current plan' : 'Sign up free'}
            </button>
          </div>
          ) : null}
          {sortedPlans.map((plan, index) => {
            const pricePerMonth =
              plan.billing_cycle === 'yearly'
                ? plan.price_cents / 12
                : plan.price_cents;

            const Icon = index === 0 ? Sparkles : index === 1 ? Zap : index === 2 ? Crown : Gem;
            const isPopular = index === 1;
            const displayName = formatPlanDisplayName(plan.name);
            const tierName = displayName.replace(/\s*\((Monthly|Yearly)\)$/i, '');

            return (
              <div
                key={plan.id}
                className={`relative rounded-2xl border-2 p-5 transition-all md:p-6 ${
                  isPopular
                    ? 'border-purple-500 bg-gradient-to-b from-purple-900/30 to-[#0c1230] shadow-xl shadow-purple-500/20'
                    : 'border-purple-500/20 bg-[#0c1230] hover:border-purple-500/40'
                }`}
              >
                {isPopular && (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-gradient-to-r from-purple-500 to-pink-500 px-3 py-1 text-sm font-medium">
                    Most Popular
                  </div>
                )}

                {/* Icon */}
                <div className="flex justify-center mb-4">
                  <div className={`p-3 rounded-full ${
                    isPopular 
                      ? 'bg-gradient-to-br from-purple-500 to-pink-500'
                      : 'bg-purple-500/20'
                  }`}>
                    <Icon className={`w-6 h-6 ${isPopular ? 'text-white' : 'text-purple-400'}`} />
                  </div>
                </div>

                {/* Plan Name */}
                <h3 className="text-xl font-display font-bold text-center mb-2">
                  {tierName}
                </h3>

                {/* Price */}
                <div className="text-center mb-6">
                  <div className="flex items-baseline justify-center gap-1">
                    <span className="text-3xl font-bold">{formatPrice(Math.floor(pricePerMonth))}</span>
                    <span className="text-gray-400">/month</span>
                  </div>
                  {plan.billing_cycle === 'yearly' && (
                    <div className="text-sm text-gray-400 mt-1">
                      {formatPrice(plan.price_cents)} billed annually
                    </div>
                  )}
                </div>

                {/* Credits */}
                <div className="text-center mb-6 pb-6 border-b border-purple-500/20">
                  <div className="text-2xl font-bold text-purple-400">
                    {creditHeadlineNumber(plan).toLocaleString()}
                  </div>
                  {creditCaptionLines(plan).map((line, index) => (
                    <div
                      key={`${line}-${index}`}
                      className={index === 0 ? "text-sm text-gray-400" : "text-xs text-gray-500 mt-1"}
                    >
                      {line}
                    </div>
                  ))}
                </div>

                {/* Features */}
                <ul className="space-y-3 mb-8">
                  {cardBulletsForPlan(plan).map((feature) => (
                    <li key={feature} className="flex items-start gap-3">
                      <Check className="w-5 h-5 text-purple-400 flex-shrink-0 mt-0.5" />
                      <span className="text-sm text-gray-300">{feature}</span>
                    </li>
                  ))}
                </ul>

                {/* CTA Button */}
                <button
                  onClick={() => handleSelectPlan(plan)}
                  disabled={purchasingPlanId === plan.id}
                  className={`w-full py-3 rounded-lg font-medium transition-all flex items-center justify-center gap-2 ${
                    isPopular
                      ? 'bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white'
                      : 'bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 border border-purple-500/30'
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  {purchasingPlanId === plan.id ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Processing...</span>
                    </>
                  ) : (
                    <span>Get {tierName}</span>
                  )}
                </button>
              </div>
            );
          })}
        </div>

        {/* FAQ / Info */}
        <div className="max-w-3xl mx-auto mt-16 text-center text-gray-400 text-sm space-y-2">
          <p>💳 All plans include secure payment processing via CutLuy</p>
          <p>🔄 Credits reset monthly • Top-up credits never expire</p>
          <p>❌ Cancel anytime • No commitment</p>
        </div>
      </div>
    </div>
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
        setPurchasingPlanId(null);
      }}
    />
    </>
  );
}
