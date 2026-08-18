'use client';

import { Check, Crown, Loader2, Sparkles, Zap } from 'lucide-react';
import {
  calculateDiscount,
  creditsToSongs,
  formatPlanDisplayName,
  formatPrice,
  type SubscriptionPlan,
} from '@/lib/subscription-api';

const PLAN_ICONS = [Sparkles, Zap, Crown];

type AvailablePlansGridProps = {
  plans: SubscriptionPlan[];
  billingCycle: 'monthly' | 'yearly';
  onBillingCycleChange: (cycle: 'monthly' | 'yearly') => void;
  currentPlanId?: string | null;
  purchasingPlanId?: string | null;
  onSelectPlan: (plan: SubscriptionPlan) => void;
};

export default function AvailablePlansGrid({
  plans,
  billingCycle,
  onBillingCycleChange,
  currentPlanId,
  purchasingPlanId,
  onSelectPlan,
}: AvailablePlansGridProps) {
  const monthlyPlans = plans.filter((plan) => plan.billing_cycle === 'monthly');
  const yearlyPlans = plans.filter((plan) => plan.billing_cycle === 'yearly');
  const displayPlans = (billingCycle === 'monthly' ? monthlyPlans : yearlyPlans).sort(
    (a, b) => a.price_cents - b.price_cents,
  );
  const yearlyDiscount =
    monthlyPlans[0] && yearlyPlans[0]
      ? calculateDiscount(monthlyPlans[0].price_cents, yearlyPlans[0].price_cents)
      : 15;

  return (
    <div>
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="font-display text-lg font-semibold text-white">Available plans</h3>
          <p className="text-sm text-slate-400">Your current plan is marked. Switch anytime.</p>
        </div>
        <div className="inline-flex items-center gap-3 self-start rounded-full border border-purple-500/20 bg-[#0c1230] p-1">
          <button
            type="button"
            onClick={() => onBillingCycleChange('monthly')}
            className={`rounded-full px-5 py-2 text-sm transition-all ${
              billingCycle === 'monthly'
                ? 'bg-gradient-to-r from-purple-500 to-pink-500 font-medium text-white'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            Monthly
          </button>
          <button
            type="button"
            onClick={() => onBillingCycleChange('yearly')}
            className={`flex items-center gap-2 rounded-full px-5 py-2 text-sm transition-all ${
              billingCycle === 'yearly'
                ? 'bg-gradient-to-r from-purple-500 to-pink-500 font-medium text-white'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            Yearly
            <span className="rounded-full bg-green-500 px-2 py-0.5 text-xs text-white">
              Save {yearlyDiscount}%
            </span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        {displayPlans.map((plan, index) => {
          const songs = creditsToSongs(plan.monthly_credits);
          const pricePerMonth =
            plan.billing_cycle === 'yearly' ? plan.price_cents / 12 : plan.price_cents;
          const Icon = PLAN_ICONS[index] || Sparkles;
          const isCurrent = Boolean(currentPlanId && plan.id === currentPlanId);
          const isPopular = !isCurrent && index === 1;
          const displayName = formatPlanDisplayName(plan.name);

          return (
            <div
              key={plan.id}
              className={`relative rounded-2xl border-2 p-6 ${
                isCurrent
                  ? 'border-green-400/50 bg-gradient-to-b from-green-900/20 to-[#0c1230]'
                  : isPopular
                    ? 'border-purple-500 bg-gradient-to-b from-purple-900/30 to-[#0c1230]'
                    : 'border-purple-500/20 bg-[#0c1230]'
              }`}
            >
              {isCurrent ? (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-green-500 px-3 py-1 text-xs font-medium text-white">
                  Current plan
                </div>
              ) : isPopular ? (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 px-3 py-1 text-xs font-medium">
                  Most Popular
                </div>
              ) : null}

              <div className="mb-3 flex justify-center">
                <div
                  className={`rounded-full p-2.5 ${
                    isCurrent || isPopular
                      ? 'bg-gradient-to-br from-purple-500 to-pink-500'
                      : 'bg-purple-500/20'
                  }`}
                >
                  <Icon className={`h-5 w-5 ${isCurrent || isPopular ? 'text-white' : 'text-purple-400'}`} />
                </div>
              </div>

              <h4 className="mb-2 text-center font-display text-xl font-bold">{displayName}</h4>
              <div className="mb-4 text-center">
                <div className="flex items-baseline justify-center gap-1">
                  <span className="text-3xl font-bold">{formatPrice(Math.floor(pricePerMonth))}</span>
                  <span className="text-gray-400">/month</span>
                </div>
                {plan.billing_cycle === 'yearly' ? (
                  <div className="mt-1 text-xs text-gray-400">
                    {formatPrice(plan.price_cents)} billed annually
                  </div>
                ) : null}
              </div>

              <div className="mb-4 border-b border-purple-500/20 pb-4 text-center">
                <div className="text-2xl font-bold text-purple-400">{songs}</div>
                <div className="text-xs text-gray-400">songs per month</div>
              </div>

              <ul className="mb-6 space-y-2">
                <li className="flex items-start gap-2 text-sm text-gray-300">
                  <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-purple-400" />
                  {songs} AI-generated songs monthly
                </li>
                {plan.features.slice(0, 3).map((feature) => (
                  <li key={feature} className="flex items-start gap-2 text-sm text-gray-300">
                    <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-purple-400" />
                    {feature}
                  </li>
                ))}
              </ul>

              <button
                type="button"
                disabled={isCurrent || purchasingPlanId === plan.id}
                onClick={() => onSelectPlan(plan)}
                className={`flex w-full items-center justify-center gap-2 rounded-lg py-3 text-sm font-medium transition-all disabled:cursor-not-allowed ${
                  isCurrent
                    ? 'border border-green-400/30 bg-green-500/15 text-green-200 disabled:opacity-100'
                    : isPopular
                      ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:from-purple-600 hover:to-pink-600 disabled:opacity-50'
                      : 'border border-purple-500/30 bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 disabled:opacity-50'
                }`}
              >
                {purchasingPlanId === plan.id ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Processing...
                  </>
                ) : isCurrent ? (
                  'Current plan'
                ) : (
                  `Switch to ${displayName.replace(/\s*\((Monthly|Yearly)\)$/i, '')}`
                )}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
