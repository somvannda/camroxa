"use client";

import { useState } from "react";
import { Check, Crown, Gift, Sparkles, Zap } from "lucide-react";

import {
  FREE_CARD_BULLETS,
  PUBLIC_CARD_BULLETS,
  calculateYearlyDiscount,
  creditsToSongs,
  formatMusicWebPrice,
  groupPublicPaidTiers,
  monthlyCreditsOf,
  publicFreePlans,
  type PublicCatalogPlan,
} from "@/lib/credits-only-public";

export type PublicPlan = PublicCatalogPlan & {
  profile_allowance?: number;
  monthly_song_limit?: number | null;
  daily_credits?: number;
};

const ICONS = [Sparkles, Zap, Crown] as const;

export function PricingCards({
  plans,
  musicWebBaseUrl,
}: {
  plans: PublicPlan[];
  musicWebBaseUrl: string;
}) {
  const [billingCycle, setBillingCycle] = useState<"monthly" | "yearly">("monthly");
  const families = groupPublicPaidTiers(plans);
  const free = (publicFreePlans(plans)[0] as PublicPlan | undefined) ?? null;
  const yearlyDiscount = (() => {
    const first = families[0];
    if (!first?.monthly || !first.yearly) return 15;
    return calculateYearlyDiscount(first.monthly.price_cents, first.yearly.price_cents);
  })();

  const signupHref = `${musicWebBaseUrl}/register`;
  const checkoutHref = `${musicWebBaseUrl}/pricing`;

  return (
    <div className="text-white">
      <div className="mb-10 text-center">
        <h1 className="mb-4 bg-gradient-to-r from-purple-400 via-pink-400 to-purple-600 bg-clip-text font-display text-5xl font-bold text-transparent">
          Choose Your Plan
        </h1>
        <p className="mx-auto mb-8 max-w-2xl text-xl text-gray-300">
          Create unlimited AI-generated music with flexible credit-based pricing
        </p>
        <div className="inline-flex items-center gap-3 rounded-full border border-purple-500/20 bg-[#0c1230] p-1">
          <button
            type="button"
            onClick={() => setBillingCycle("monthly")}
            className={`rounded-full px-6 py-2 transition-all ${
              billingCycle === "monthly"
                ? "bg-gradient-to-r from-purple-500 to-pink-500 font-medium text-white"
                : "text-gray-400 hover:text-white"
            }`}
          >
            Monthly
          </button>
          <button
            type="button"
            onClick={() => setBillingCycle("yearly")}
            className={`flex items-center gap-2 rounded-full px-6 py-2 transition-all ${
              billingCycle === "yearly"
                ? "bg-gradient-to-r from-purple-500 to-pink-500 font-medium text-white"
                : "text-gray-400 hover:text-white"
            }`}
          >
            Yearly
            <span className="rounded-full bg-green-500 px-2 py-0.5 text-xs text-white">
              Save {yearlyDiscount}%
            </span>
          </button>
        </div>
      </div>

      <div
        className={`mx-auto grid max-w-6xl grid-cols-1 gap-6 ${
          free ? "md:grid-cols-2 xl:grid-cols-4" : "md:grid-cols-3"
        }`}
      >
        {free ? (
          <article className="relative rounded-2xl border-2 border-purple-500/20 bg-[#0c1230] p-6 md:p-8">
            <div className="mb-4 flex justify-center">
              <div className="rounded-full bg-purple-500/20 p-3">
                <Gift className="h-6 w-6 text-purple-400" />
              </div>
            </div>
            <h3 className="mb-2 text-center font-display text-2xl font-bold">Free</h3>
            <div className="mb-6 text-center">
              <div className="flex items-baseline justify-center gap-1">
                <span className="text-4xl font-bold">$0</span>
                <span className="text-gray-400">/month</span>
              </div>
            </div>
            <div className="mb-6 border-b border-purple-500/20 pb-6 text-center">
              <div className="text-3xl font-bold text-purple-400">
                {Number(free.daily_credits || free.monthly_credits || 0)}
              </div>
              <div className="text-sm text-gray-400">
                {Number(free.daily_credits || 0) > 0 ? "daily credits" : "credits"}
              </div>
              <div className="mt-1 text-xs text-gray-500">Resets at midnight</div>
            </div>
            <ul className="mb-8 space-y-3">
              {FREE_CARD_BULLETS.map((feature) => (
                <li key={feature} className="flex items-start gap-3">
                  <Check className="mt-0.5 h-5 w-5 flex-shrink-0 text-purple-400" />
                  <span className="text-sm text-gray-300">{feature}</span>
                </li>
              ))}
            </ul>
            <a
              href={signupHref}
              className="block w-full rounded-lg border border-purple-500/30 bg-purple-500/20 py-3 text-center font-medium text-purple-300 transition-all hover:bg-purple-500/30"
            >
              Sign up free
            </a>
          </article>
        ) : null}

        {families.map((family, index) => {
          const plan = (
            billingCycle === "yearly"
              ? family.yearly ?? family.monthly ?? family.representative
              : family.monthly ?? family.yearly ?? family.representative
          ) as PublicPlan;
          const credits = monthlyCreditsOf(plan);
          const songs = creditsToSongs(credits);
          const isPopular = index === 1;
          const Icon = ICONS[Math.min(index, ICONS.length - 1)];
          const pricePerMonth =
            billingCycle === "yearly" && family.yearly
              ? plan.price_cents / 12
              : plan.price_cents;

          return (
            <article
              key={family.key}
              className={`relative rounded-2xl border-2 p-6 transition-all md:p-8 ${
                isPopular
                  ? "border-purple-500 bg-gradient-to-b from-purple-900/30 to-[#0c1230] shadow-xl shadow-purple-500/20"
                  : "border-purple-500/20 bg-[#0c1230] hover:border-purple-500/40"
              }`}
            >
              {isPopular ? (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 px-4 py-1 text-sm font-medium">
                  Most Popular
                </div>
              ) : null}
              <div className="mb-4 flex justify-center">
                <div
                  className={`rounded-full p-3 ${
                    isPopular
                      ? "bg-gradient-to-br from-purple-500 to-pink-500"
                      : "bg-purple-500/20"
                  }`}
                >
                  <Icon className={`h-6 w-6 ${isPopular ? "text-white" : "text-purple-400"}`} />
                </div>
              </div>
              <h3 className="mb-2 text-center font-display text-2xl font-bold">{family.label}</h3>
              <div className="mb-6 text-center">
                <div className="flex items-baseline justify-center gap-1">
                  <span className="text-4xl font-bold">
                    {formatMusicWebPrice(Math.floor(pricePerMonth))}
                  </span>
                  <span className="text-gray-400">/month</span>
                </div>
                {billingCycle === "yearly" && family.yearly ? (
                  <div className="mt-1 text-sm text-gray-400">
                    {formatMusicWebPrice(plan.price_cents)} billed annually
                  </div>
                ) : null}
              </div>
              <div className="mb-6 border-b border-purple-500/20 pb-6 text-center">
                <div className="text-3xl font-bold text-purple-400">
                  {credits.toLocaleString()}
                </div>
                <div className="text-sm text-gray-400">credits per month</div>
                <div className="mt-1 text-xs text-gray-500">≈ {songs} songs/mo</div>
              </div>
              <ul className="mb-8 space-y-3">
                {PUBLIC_CARD_BULLETS.map((feature) => (
                  <li key={feature} className="flex items-start gap-3">
                    <Check className="mt-0.5 h-5 w-5 flex-shrink-0 text-purple-400" />
                    <span className="text-sm text-gray-300">{feature}</span>
                  </li>
                ))}
              </ul>
              <a
                href={checkoutHref}
                className={`block w-full rounded-lg py-3 text-center font-medium transition-all ${
                  isPopular
                    ? "bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:from-purple-600 hover:to-pink-600"
                    : "border border-purple-500/30 bg-purple-500/20 text-purple-300 hover:bg-purple-500/30"
                }`}
              >
                Get {family.label}
              </a>
            </article>
          );
        })}
      </div>

      <div className="mx-auto mt-16 max-w-3xl space-y-2 text-center text-sm text-gray-400">
        <p>💳 All plans include secure payment processing via CutLuy</p>
        <p>🔄 Credits reset monthly • Top-up credits never expire</p>
        <p>❌ Cancel anytime • No commitment</p>
      </div>
    </div>
  );
}
