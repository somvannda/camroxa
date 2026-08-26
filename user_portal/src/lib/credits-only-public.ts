/** Public catalog helpers — Starter / Creator / Studio (+ Free only if public). */

export const CREDITS_PER_GENERATE = 10;
export const SONGS_PER_GENERATE = 2;
export const CREDITS_PER_SONG = CREDITS_PER_GENERATE;

export const PUBLIC_CARD_BULLETS = [
  'Web Create',
  'Desktop studio',
  'Dual channels',
  'Top-up packs',
] as const;

export const FREE_CARD_BULLETS = [
  'Web Create',
  'Daily credit reset',
  'Top-up packs',
] as const;

export const TIER_ORDER = ['starter', 'creator', 'studio'] as const;

export type PublicCatalogPlan = {
  id: string;
  name: string;
  price_cents: number;
  effective_price_cents: number;
  billing_cycle_days?: number | null;
  monthly_credits?: number;
  daily_credits?: number;
  monthly_song_limit?: number | null;
  pricing_features?: string[];
  pricing_credit_lines?: string[];
  features?: string[];
  credits_per_generate?: number;
};

export function creditsToSongs(
  credits: number,
  creditsPerGenerate: number = CREDITS_PER_GENERATE,
): number {
  const per = Number(creditsPerGenerate) > 0 ? Number(creditsPerGenerate) : CREDITS_PER_GENERATE;
  return Math.floor(Math.max(0, Number(credits) || 0) / per) * SONGS_PER_GENERATE;
}

export function creditHeadlineNumber(plan: Pick<PublicCatalogPlan, "monthly_credits" | "daily_credits">): number {
  const daily = Number(plan.daily_credits || 0);
  if (daily > 0) return daily;
  return Number(plan.monthly_credits || 0);
}

export function creditCaptionLines(plan: Pick<PublicCatalogPlan, "monthly_credits" | "daily_credits" | "pricing_credit_lines" | "credits_per_generate">): string[] {
  const unique = [
    ...new Set((plan.pricing_credit_lines ?? []).map((line) => String(line).trim()).filter(Boolean)),
  ];
  if (unique.length) return unique;
  const daily = Number(plan.daily_credits || 0);
  const monthly = Number(plan.monthly_credits || 0);
  const perGenerate = plan.credits_per_generate;
  if (daily > 0) {
    return [
      "daily credits",
      `≈ ${creditsToSongs(daily, perGenerate).toLocaleString("en-US")} songs/day`,
      "Resets at midnight",
    ];
  }
  if (monthly > 0) {
    return [
      "credits per month",
      `≈ ${creditsToSongs(monthly, perGenerate).toLocaleString("en-US")} songs/mo`,
    ];
  }
  return ["credits"];
}

export function cardBulletsForPlan(plan: PublicCatalogPlan): string[] {
  const raw = plan.pricing_features?.length ? plan.pricing_features : plan.features;
  const unique = [...new Set((raw ?? []).map((line) => String(line).trim()).filter(Boolean))];
  if (unique.length) return unique;
  const name = (plan.name || '').toLowerCase();
  if (Number(plan.price_cents) <= 0 && name.includes('free')) {
    return [...FREE_CARD_BULLETS];
  }
  return [...PUBLIC_CARD_BULLETS];
}

export function isHiddenLegacyPrice(plan: PublicCatalogPlan): boolean {
  return Number(plan.price_cents) === 7900 || Number(plan.effective_price_cents) === 7900;
}

export function planTierKey(name: string): string {
  const n = (name || '').toLowerCase();
  if (n.includes('starter')) return 'starter';
  if (n.includes('creator')) return 'creator';
  if (n.includes('studio')) return 'studio';
  if (/\bfree\b/.test(n)) return 'free';
  return n.replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'plan';
}

export function displayPlanName(name: string): string {
  const key = planTierKey(name);
  if (key === 'starter') return 'Starter';
  if (key === 'creator') return 'Creator';
  if (key === 'studio') return 'Studio';
  if (key === 'free') return 'Free';
  return (name || 'Plan')
    .replace(/\s*\((monthly|yearly|annual|6.?month)\)\s*$/i, '')
    .replace(/[-_\s]+(monthly|yearly)$/i, '')
    .trim();
}

export function monthlyCreditsOf(plan: PublicCatalogPlan): number {
  if (plan.monthly_credits != null && Number(plan.monthly_credits) > 0) {
    return Math.floor(Number(plan.monthly_credits));
  }
  const key = planTierKey(plan.name);
  if (key === 'starter') return 1000;
  if (key === 'creator') return 3500;
  if (key === 'studio') return 8000;
  return 0;
}

export function publicPaidPlans(plans: PublicCatalogPlan[]): PublicCatalogPlan[] {
  return plans.filter(
    (plan) =>
      Number(plan.effective_price_cents ?? plan.price_cents) > 0 && !isHiddenLegacyPrice(plan),
  );
}

export function publicFreePlans(plans: PublicCatalogPlan[]): PublicCatalogPlan[] {
  return plans.filter(
    (plan) =>
      Number(plan.effective_price_cents ?? plan.price_cents) <= 0 &&
      planTierKey(plan.name) === 'free' &&
      !isHiddenLegacyPrice(plan),
  );
}

export function isMonthlyPlan(plan: PublicCatalogPlan): boolean {
  const days = plan.billing_cycle_days;
  return days == null || days === 30;
}

export function isYearlyPlan(plan: PublicCatalogPlan): boolean {
  return plan.billing_cycle_days === 365;
}

export type PublicTierFamily = {
  key: string;
  label: string;
  monthly: PublicCatalogPlan | null;
  yearly: PublicCatalogPlan | null;
  representative: PublicCatalogPlan;
};

export function groupPublicPaidTiers(plans: PublicCatalogPlan[]): PublicTierFamily[] {
  const paid = publicPaidPlans(plans);
  const buckets = new Map<string, PublicCatalogPlan[]>();
  for (const plan of paid) {
    const key = planTierKey(plan.name);
    const list = buckets.get(key) ?? [];
    list.push(plan);
    buckets.set(key, list);
  }

  const keys = [
    ...TIER_ORDER.filter((key) => buckets.has(key)),
    ...[...buckets.keys()].filter((key) => !(TIER_ORDER as readonly string[]).includes(key)).sort(),
  ];

  return keys.map((key) => {
    const bucket = buckets.get(key) ?? [];
    const monthly = bucket.find(isMonthlyPlan) ?? null;
    const yearly = bucket.find(isYearlyPlan) ?? null;
    const representative = monthly ?? yearly ?? bucket[0];
    return {
      key,
      label: displayPlanName(representative.name),
      monthly,
      yearly,
      representative,
    };
  });
}
