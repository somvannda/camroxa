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
