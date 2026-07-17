/** Markup / margin math for admin credit pricing (display credits). */

export function computeMargins(
  pricingCredits: number,
  costCredits: number,
  globalCreditValue: number | null,
) {
  if (globalCreditValue === null || globalCreditValue <= 0) {
    return {
      sellPriceDollars: null,
      costDollars: null,
      profitDollars: null,
      profitPercentOnCost: null,
      profitPercentOnRevenue: null,
      chargeMultiplier: null,
    };
  }
  const sellPriceDollars = pricingCredits * globalCreditValue;
  const costDollars = costCredits * globalCreditValue;
  const profitDollars = sellPriceDollars - costDollars;
  const profitPercentOnRevenue = sellPriceDollars > 0
    ? Math.round((profitDollars / sellPriceDollars) * 100 * 100) / 100
    : 0;
  const profitPercentOnCost =
    costCredits > 0 && pricingCredits > 0
      ? marginFromPricing(costCredits, pricingCredits)
      : null;
  const chargeMultiplier =
    costCredits > 0 && pricingCredits > 0
      ? Math.round((pricingCredits / costCredits) * 100) / 100
      : null;
  return {
    sellPriceDollars,
    costDollars,
    profitDollars,
    profitPercentOnCost,
    profitPercentOnRevenue,
    chargeMultiplier,
  };
}

/** Markup % on cost (e.g. 100 = profit equals cost, 1000 = profit is 10× cost). */
export function pricingFromMargin(costCredits: number, marginPercent: number): number {
  if (!Number.isFinite(costCredits) || costCredits < 0) return 0.0001;
  if (!Number.isFinite(marginPercent) || marginPercent < 0) {
    return Math.max(0.0001, costCredits);
  }
  const pricing = costCredits * (1 + marginPercent / 100);
  return roundPricingCredits(Math.max(pricing, costCredits));
}

/** Markup % on cost from cost and pricing credits (unbounded; 200 = 3× cost). */
export function marginFromPricing(costCredits: number, pricingCredits: number): number {
  if (!Number.isFinite(costCredits) || costCredits <= 0) return 0;
  if (!Number.isFinite(pricingCredits) || pricingCredits <= 0) return 0;
  const markup = ((pricingCredits / costCredits) - 1) * 100;
  if (!Number.isFinite(markup)) return 0;
  return Math.round(markup * 100) / 100;
}

/** Round up to micro-credit precision (matches backend pricing generator). */
export function roundPricingCredits(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 0.0001;
  const units = Math.ceil(value * 10_000);
  return units / 10_000;
}
