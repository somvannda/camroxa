export const FREE_CARD_BULLETS = [
  'Web Create',
  'Daily credit reset',
  'Top-up packs',
] as const;

export const FREE_MONTHLY_CARD_BULLETS = [
  'Web Create',
  'Monthly credit reset',
  'Top-up packs',
] as const;

export const PUBLIC_CARD_BULLETS = [
  'Web Create',
  'Desktop studio',
  'Dual channels',
  'Top-up packs',
] as const;

export function normalizeFeatureLines(value?: string[] | null): string[] {
  return [...new Set((value ?? []).map((line) => String(line).trim()).filter(Boolean))];
}

export function cardBulletsForPlan(plan: {
  name: string;
  price_cents: number;
  features?: string[];
  pricing_features?: string[];
  daily_credits?: number;
  monthly_credits?: number;
}): readonly string[] {
  const fromApi = normalizeFeatureLines(plan.pricing_features ?? plan.features);
  if (fromApi.length) return fromApi;
  const name = plan.name.replace(/[_-]/g, ' ').toLowerCase();
  if (plan.price_cents <= 0 && name.includes('free')) {
    if (Number(plan.daily_credits || 0) > 0) return FREE_CARD_BULLETS;
    if (Number(plan.monthly_credits || 0) > 0) return FREE_MONTHLY_CARD_BULLETS;
    return ['Web Create', 'Top-up packs'];
  }
  return PUBLIC_CARD_BULLETS;
}

export function creditResetLabel(plan: {
  daily_credits?: number;
  monthly_credits?: number;
  reset_label?: string | null;
}): string | null {
  const provided = typeof plan.reset_label === 'string' ? plan.reset_label.trim() : plan.reset_label;
  if (provided === null) return null;
  if (provided) return provided;
  const daily = Number(plan.daily_credits || 0);
  const monthly = Number(plan.monthly_credits || 0);
  if (daily > 0) return 'Credit reset daily';
  if (monthly > 0) return 'Credit reset monthly';
  return null;
}

/** Wallet fields the header card needs. Structurally compatible with `CreditBalance`. */
export type CreditDisplayInput = {
  total_credits: number;
  monthly_credits: number;
  monthly_credits_used: number;
  topup_credits: number;
  daily_free_credits: number;
  daily_free_limit: number;
  has_subscription: boolean;
  grant_remaining?: number;
  reset_label?: string | null;
};

export type CreditDisplay = {
  used: number;
  limit: number;
  remaining: number;
  progressPct: number;
  resetLabel: string | null;
  promoText: string | null;
  isLow: boolean;
  hasSubscription: boolean;
};

/**
 * Derive the header/sidebar credit card numbers from a wallet balance.
 *
 * The plan's monthly pool is only a floor, not the spendable balance: a free
 * user can hold stacked grants and top-ups above it. Showing `grant_remaining`
 * (clamped to the pool) froze the card while credits were really being debited,
 * so the free case now reports the authoritative `total_credits` and a capacity
 * that cannot sit below it.
 */
export function computeCreditDisplay(balance: CreditDisplayInput | null): CreditDisplay {
  if (!balance) {
    return {
      used: 0,
      limit: 50,
      remaining: 0,
      progressPct: 0,
      resetLabel: null,
      promoText: 'Buy a credit pack to keep creating.',
      isLow: true,
      hasSubscription: false,
    };
  }

  const resetLabel = creditResetLabel({
    daily_credits: balance.daily_free_limit,
    monthly_credits: balance.monthly_credits,
    reset_label: balance.reset_label,
  });

  if (balance.has_subscription) {
    const remaining = Math.max(0, balance.total_credits);
    // `monthly_credits` is the granted pool, not the remainder. Adding
    // `monthly_credits_used` (already pool - remaining) double-counted the pool,
    // so a 1,000-credit plan with 1 credit left showed a 1,999 capacity. The
    // pool plus top-ups is the real capacity.
    const capacity = Math.max(
      remaining,
      balance.monthly_credits + balance.topup_credits,
      1,
    );
    return {
      used: remaining,
      limit: capacity,
      remaining,
      progressPct: Math.min(100, Math.round((remaining / capacity) * 100)),
      resetLabel,
      promoText:
        balance.topup_credits > 0
          ? `Includes ${balance.topup_credits.toLocaleString('en-US')} top-up credits`
          : null,
      isLow: remaining > 0 && remaining < 30,
      hasSubscription: true,
    };
  }

  const dailyLimit = Math.max(0, balance.daily_free_limit);
  const monthlyLimit = Math.max(0, balance.monthly_credits);
  const planAllowance = dailyLimit > 0 ? dailyLimit : monthlyLimit;
  const remaining = Math.max(0, balance.total_credits);
  const limit = Math.max(planAllowance, remaining, 1);

  return {
    used: remaining,
    limit,
    remaining,
    progressPct: Math.min(100, Math.round((remaining / limit) * 100)),
    resetLabel,
    promoText:
      balance.topup_credits > 0
        ? `Includes ${balance.topup_credits.toLocaleString('en-US')} top-up credits`
        : 'Buy a credit pack to keep creating.',
    isLow: remaining > 0 && remaining < 30,
    hasSubscription: false,
  };
}
