import type { PublicPlan } from "@/lib/billing";
import { billingTermQuotes, formatPlanPrice, type PlanTermDiscounts } from "@/lib/plan-pricing";

export const BILLING_TERM_DAYS = {
  monthly: 30,
  semiAnnual: 180,
  annual: 365,
} as const;

export type BillingTermKey = keyof typeof BILLING_TERM_DAYS;

export type ChannelPlanFamily = {
  channels: number;
  monthly: PublicPlan | null;
  semiAnnual: PublicPlan | null;
  annual: PublicPlan | null;
  representative: PublicPlan;
};

function planForTerm(group: PublicPlan[], billingCycleDays: number): PublicPlan | null {
  return group.find((plan) => plan.billing_cycle_days === billingCycleDays) ?? null;
}

export function groupPlansIntoChannelFamilies(plans: PublicPlan[]): ChannelPlanFamily[] {
  const paidPlans = plans.filter((plan) => plan.effective_price_cents > 0);
  const grouped = new Map<number, PublicPlan[]>();

  for (const plan of paidPlans) {
    const channels = plan.profile_allowance;
    const bucket = grouped.get(channels) ?? [];
    bucket.push(plan);
    grouped.set(channels, bucket);
  }

  return [...grouped.entries()]
    .sort(([left], [right]) => left - right)
    .map(([channels, bucket]) => {
      const monthly = planForTerm(bucket, BILLING_TERM_DAYS.monthly);
      const semiAnnual = planForTerm(bucket, BILLING_TERM_DAYS.semiAnnual);
      const annual = planForTerm(bucket, BILLING_TERM_DAYS.annual);
      const representative = monthly ?? semiAnnual ?? annual ?? bucket[0];

      return {
        channels,
        monthly,
        semiAnnual,
        annual,
        representative,
      };
    });
}

export function channelFamilyLabel(channels: number): string {
  return `${channels.toLocaleString()} Channel${channels === 1 ? "" : "s"}`;
}

export function planForFamilyTerm(
  family: ChannelPlanFamily,
  term: BillingTermKey,
): PublicPlan | null {
  return term === "monthly" ? family.monthly : term === "semiAnnual" ? family.semiAnnual : family.annual;
}

export function termPriceCents(family: ChannelPlanFamily, term: BillingTermKey): number | null {
  const plan =
    term === "monthly" ? family.monthly : term === "semiAnnual" ? family.semiAnnual : family.annual;
  return plan?.effective_price_cents ?? null;
}

export function billingPriceLabel(
  family: ChannelPlanFamily,
  term: BillingTermKey,
  termDiscounts: PlanTermDiscounts,
): string {
  const monthly = termPriceCents(family, "monthly");
  if (monthly == null) return "—";
  if (term === "monthly") {
    return formatPlanPrice(monthly);
  }
  const quotes = billingTermQuotes(monthly, termDiscounts);
  const total = term === "semiAnnual" ? quotes.semiAnnual : quotes.annual;
  return formatPlanPrice(total);
}

export { formatPlanPrice };

export function formatPlanTermLabel(term: BillingTermKey, termDiscounts: { semi_annual_discount_percent: number; annual_discount_percent: number }): string {
  if (term === "monthly") return "Monthly";
  if (term === "semiAnnual") {
    return `6 Months (${termDiscounts.semi_annual_discount_percent}% off)`;
  }
  return `Annual (${termDiscounts.annual_discount_percent}% off)`;
}

export function formatPlanBillingCaption(plan: PublicPlan): string {
  const days = plan.billing_cycle_days;
  if (days === null) return "One-time";
  if (days === 30) return "per month";
  if (days === 365) return "per year";
  if (days === 180) return "every 6 months";
  return `every ${days} days`;
}

function formatLimit(value: number | null): string {
  return value === null ? "Unlimited" : value.toLocaleString();
}

export function planHighlightLines(plan: PublicPlan): string[] {
  return [
    `${plan.profile_allowance.toLocaleString()} channel profile${plan.profile_allowance === 1 ? "" : "s"}`,
    `${formatLimit(plan.monthly_song_limit)} Suno packages / month`,
    `${formatLimit(plan.monthly_image_limit)} images / month`,
    "Desktop Studio + guided onboarding",
  ];
}
