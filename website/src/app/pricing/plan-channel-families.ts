import type { PublicPlan } from "@/app/pricing/pricing-comparison-table";

export const BILLING_TERM_DAYS = {
  monthly: 30,
  semiAnnual: 180,
  annual: 365,
} as const;

export type ChannelPlanFamily = {
  channels: number;
  monthly: PublicPlan | null;
  semiAnnual: PublicPlan | null;
  annual: PublicPlan | null;
  /** Monthly plan used for feature comparison; falls back to any term. */
  representative: PublicPlan;
};

function planForTerm(group: PublicPlan[], billingCycleDays: number): PublicPlan | null {
  return group.find((plan) => plan.billing_cycle_days === billingCycleDays) ?? null;
}

/** Group purchasable plans by channel count (profile_allowance). */
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

export { formatPlanPrice } from "@/lib/plan-pricing";

export function termPriceCents(family: ChannelPlanFamily, term: keyof typeof BILLING_TERM_DAYS): number | null {
  const plan =
    term === "monthly"
      ? family.monthly
      : term === "semiAnnual"
        ? family.semiAnnual
        : family.annual;
  return plan?.effective_price_cents ?? null;
}
