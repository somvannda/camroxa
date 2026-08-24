/** Public catalog helpers — Starter / Creator / Studio (+ Free only if public). */

export const CREDITS_PER_SONG = 10;

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
};

export function creditsToSongs(credits: number): number {
  return Math.floor(Math.max(0, Number(credits) || 0) / CREDITS_PER_SONG);
}

export function formatMusicWebPrice(cents: number): string {
  return `$${(Number(cents) / 100).toFixed(2)}`;
}

export function calculateYearlyDiscount(monthlyCents: number, yearlyCents: number): number {
  const yearlyMonthlyEquivalent = Number(monthlyCents) * 12;
  if (yearlyMonthlyEquivalent <= 0) return 15;
  return Math.round(((yearlyMonthlyEquivalent - Number(yearlyCents)) / yearlyMonthlyEquivalent) * 100);
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
