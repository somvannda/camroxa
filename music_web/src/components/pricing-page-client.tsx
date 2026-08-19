'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Check, Sparkles, Zap, Crown, Loader2 } from 'lucide-react';
import {
  fetchSubscriptionPlans,
  purchaseSubscription,
  formatPrice,
  formatPlanDisplayName,
  calculateDiscount,
  creditsToSongs,
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
  const [checkoutPaymentId, setCheckoutPaymentId] = useState<string | null>(null);
  const [checkoutPlan, setCheckoutPlan] = useState<{ name: string; price: string } | null>(null);

  useEffect(() => {
    loadPlans();
  }, []);

  async function loadPlans() {
    try {
      const { plans: allPlans } = await fetchSubscriptionPlans();
      setPlans(allPlans.filter((p) => p.is_public));
    } catch (err) {
      console.error('Failed to load plans:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleSelectPlan(plan: SubscriptionPlan) {
    if (!user) {
      router.push(`/login?redirect=/pricing`);
      return;
    }

    setPurchasingPlanId(plan.id);

    try {
      const currentUrl = window.location.origin;
      const { checkout_url, payment_id } = await purchaseSubscription({
        plan_id: plan.id,
        success_url: `${currentUrl}/create`,
        cancel_url: `${currentUrl}/create`,
      });

      setCheckoutPlan({
        name: formatPlanDisplayName(plan.name),
        price: formatPrice(plan.price_cents),
      });
      setCheckoutPaymentId(payment_id);
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
  const sortedPlans = [...displayPlans].sort((a, b) => a.price_cents - b.price_cents);

  // Calculate yearly discount
  const yearlyDiscount = monthlyPlans[0] && yearlyPlans[0]
    ? calculateDiscount(monthlyPlans[0].price_cents, yearlyPlans[0].price_cents)
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
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto">
          {sortedPlans.map((plan, index) => {
            const songs = creditsToSongs(plan.monthly_credits);
            const pricePerMonth =
              plan.billing_cycle === 'yearly'
                ? plan.price_cents / 12
                : plan.price_cents;

            const Icon = index === 0 ? Sparkles : index === 1 ? Zap : Crown;
            const isPopular = index === 1;
            const displayName = formatPlanDisplayName(plan.name);

            return (
              <div
                key={plan.id}
                className={`relative rounded-2xl p-8 border-2 transition-all hover:scale-105 ${
                  isPopular
                    ? 'border-purple-500 bg-gradient-to-b from-purple-900/30 to-[#0c1230] shadow-xl shadow-purple-500/20'
                    : 'border-purple-500/20 bg-[#0c1230] hover:border-purple-500/40'
                }`}
              >
                {isPopular && (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1 bg-gradient-to-r from-purple-500 to-pink-500 rounded-full text-sm font-medium">
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
                <h3 className="text-2xl font-display font-bold text-center mb-2">
                  {displayName}
                </h3>

                {/* Price */}
                <div className="text-center mb-6">
                  <div className="flex items-baseline justify-center gap-1">
                    <span className="text-4xl font-bold">{formatPrice(Math.floor(pricePerMonth))}</span>
                    <span className="text-gray-400">/month</span>
                  </div>
                  {plan.billing_cycle === 'yearly' && (
                    <div className="text-sm text-gray-400 mt-1">
                      {formatPrice(plan.price_cents)} billed annually
                    </div>
                  )}
                </div>

                {/* Songs */}
                <div className="text-center mb-6 pb-6 border-b border-purple-500/20">
                  <div className="text-3xl font-bold text-purple-400">{songs}</div>
                  <div className="text-sm text-gray-400">songs per month</div>
                  <div className="text-xs text-gray-500 mt-1">
                    {plan.monthly_credits.toLocaleString()} credits
                  </div>
                </div>

                {/* Features */}
                <ul className="space-y-3 mb-8">
                  <li className="flex items-start gap-3">
                    <Check className="w-5 h-5 text-purple-400 flex-shrink-0 mt-0.5" />
                    <span className="text-sm text-gray-300">
                      {songs} AI-generated songs monthly
                    </span>
                  </li>
                  {plan.features.map((feature, idx) => (
                    <li key={idx} className="flex items-start gap-3">
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
                    <span>Get {displayName}</span>
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
