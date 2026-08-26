"use client";

import * as React from "react";
import Link from "next/link";
import { Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { PublicPlan } from "@/lib/billing";
import {
  cardBulletsForPlan,
  creditCaptionLines,
  creditHeadlineNumber,
  groupPublicPaidTiers,
  publicFreePlans,
} from "@/lib/credits-only-public";
import { formatPlanPrice, type PlanTermDiscounts } from "@/lib/plan-pricing";

type OnboardingPlanPickerProps = {
  plans: PublicPlan[];
  termDiscounts: PlanTermDiscounts;
  pricingPageUrl: string;
  paidCheckoutAvailable: boolean;
  creatingPayment: boolean;
  selectedPlanId: string | null;
  onSelectPlan: (planId: string) => void;
};

function CardBullets({ plan }: { plan: PublicPlan }) {
  return (
    <ul className="mb-5 space-y-2">
      {cardBulletsForPlan(plan).map((feature) => (
        <li key={feature} className="flex items-start gap-2 text-sm text-slate-200/82">
          <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-emerald-300/20 bg-emerald-400/10 text-emerald-100">
            <Check className="h-3 w-3" aria-hidden="true" />
          </span>
          <span>{feature}</span>
        </li>
      ))}
    </ul>
  );
}

export function OnboardingPlanPicker({
  plans,
  termDiscounts,
  pricingPageUrl,
  paidCheckoutAvailable,
  creatingPayment,
  selectedPlanId,
  onSelectPlan,
}: OnboardingPlanPickerProps) {
  const [term, setTerm] = React.useState<"monthly" | "yearly">("monthly");
  const families = React.useMemo(() => groupPublicPaidTiers(plans), [plans]);
  const free = React.useMemo(() => publicFreePlans(plans)[0] as PublicPlan | undefined, [plans]);

  if (families.length === 0 && !free) {
    return (
      <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-6 text-sm text-slate-200/72">
        No subscription plans are available right now. Please try again later or contact support.
      </div>
    );
  }

  const yearlyDiscount = termDiscounts.annual_discount_percent;

  return (
    <div className="grid gap-4">
      <div className="flex justify-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] p-1">
          <button
            type="button"
            onClick={() => setTerm("monthly")}
            className={cn(
              "rounded-full px-4 py-1.5 text-sm",
              term === "monthly" ? "bg-white/10 text-white" : "text-slate-400",
            )}
          >
            Monthly
          </button>
          <button
            type="button"
            onClick={() => setTerm("yearly")}
            className={cn(
              "rounded-full px-4 py-1.5 text-sm",
              term === "yearly" ? "bg-white/10 text-white" : "text-slate-400",
            )}
          >
            Yearly
            <span className="ml-2 rounded-full bg-emerald-500/80 px-2 py-0.5 text-[11px] text-white">
              Save {yearlyDiscount}%
            </span>
          </button>
        </div>
      </div>

      <div className={`grid gap-5 ${free ? "md:grid-cols-2 xl:grid-cols-4" : "md:grid-cols-3"}`}>
        {free ? (
          <article className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 ring-1 ring-white/6">
            <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Free</div>
            <h3 className="mt-2 font-display text-2xl font-semibold text-white">Free</h3>
            <div className="mt-4 text-4xl font-semibold text-white">$0</div>
            <div className="mt-4 border-b border-white/8 pb-4">
              <div className="text-3xl font-semibold text-emerald-200">
                {creditHeadlineNumber(free).toLocaleString()}
              </div>
              {creditCaptionLines(free).map((line, index) => (
                <div
                  key={`${line}-${index}`}
                  className={index === 0 ? "text-sm text-slate-400" : "mt-1 text-xs text-slate-500"}
                >
                  {line}
                </div>
              ))}
            </div>
            <div className="mt-4">
              <CardBullets plan={free} />
            </div>
            <p className="text-sm text-slate-400">Shown only because Free is public. Continue with a paid plan to checkout.</p>
          </article>
        ) : null}

        {families.map((family, index) => {
          const plan = (term === "yearly" ? family.yearly ?? family.monthly : family.monthly ?? family.representative) as PublicPlan | null;
          if (!plan) return null;
          const featured = index === 1;
          const loading = Boolean(creatingPayment && selectedPlanId === plan.id);
          const price =
            term === "yearly" && family.yearly
              ? formatPlanPrice(family.yearly.effective_price_cents)
              : formatPlanPrice((family.monthly ?? plan).effective_price_cents);
          return (
            <article
              key={family.key}
              className={cn(
                "rounded-[28px] border p-6 ring-1",
                featured
                  ? "border-emerald-300/30 bg-[linear-gradient(180deg,rgba(16,185,129,0.14),rgba(255,255,255,0.03))] ring-emerald-400/15"
                  : "border-white/10 bg-white/[0.03] ring-white/6",
              )}
            >
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                {featured ? "Most popular" : "Plan"}
              </div>
              <h3 className="mt-2 font-display text-2xl font-semibold text-white">{family.label}</h3>
              <div className="mt-4 flex items-baseline gap-1">
                <span className="text-4xl font-semibold text-white">{price}</span>
                <span className="text-slate-400">{term === "yearly" && family.yearly ? "/year" : "/month"}</span>
              </div>
              <div className="mt-5 border-b border-white/8 pb-5">
                <div className="text-3xl font-semibold text-emerald-200">
                  {creditHeadlineNumber(plan).toLocaleString()}
                </div>
                {creditCaptionLines(plan).map((line, index) => (
                  <div
                    key={`${line}-${index}`}
                    className={index === 0 ? "text-sm text-slate-400" : "mt-1 text-xs text-slate-500"}
                  >
                    {line}
                  </div>
                ))}
              </div>
              <CardBullets plan={plan} />
              <Button
                type="button"
                className="w-full bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 text-white"
                onClick={() => onSelectPlan(plan.id)}
                disabled={!paidCheckoutAvailable || creatingPayment}
              >
                {loading ? "Starting checkout..." : paidCheckoutAvailable ? "Continue" : "Unavailable"}
              </Button>
            </article>
          );
        })}
      </div>

      <div className="text-center text-sm text-slate-300/72">
        Same three public cards as{" "}
        <Link
          href={pricingPageUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-white underline-offset-4 hover:underline"
        >
          the public pricing page
        </Link>
        . Hidden $79 and unpublished dual-profile packs are not listed.
      </div>
    </div>
  );
}
