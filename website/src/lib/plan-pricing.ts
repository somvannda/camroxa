/** Shared plan price formatting — matches admin portal (whole dollars, no cents). */

export type PlanTermDiscounts = {
  semi_annual_discount_percent: number;
  annual_discount_percent: number;
};

export const DEFAULT_TERM_DISCOUNTS: PlanTermDiscounts = {
  semi_annual_discount_percent: 15,
  annual_discount_percent: 25,
};

export function roundWholeDollars(cents: number): number {
  if (cents <= 0) return 0;
  return Math.ceil(cents / 100) * 100;
}

/** Format checkout cents as whole-dollar USD (same as admin Plans page). */
export function formatPlanPrice(cents: number): string {
  const wholeCents = roundWholeDollars(cents);
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(wholeCents / 100);
}

export function billingTermTotalCents(
  monthlyCents: number,
  months: number,
  discountPercent: number,
): number {
  return roundWholeDollars(Math.round(monthlyCents * months * (1 - discountPercent / 100)));
}

const SEMI_ANNUAL_MONTHS = 6;
const ANNUAL_MONTHS = 12;

/** Match admin portal billing term math — monthly row + saved discount %. */
export function billingTermQuotes(
  monthlyCents: number,
  termDiscounts: PlanTermDiscounts = DEFAULT_TERM_DISCOUNTS,
) {
  const monthly = roundWholeDollars(monthlyCents);
  return {
    monthly,
    semiAnnual: billingTermTotalCents(
      monthly,
      SEMI_ANNUAL_MONTHS,
      termDiscounts.semi_annual_discount_percent,
    ),
    annual: billingTermTotalCents(
      monthly,
      ANNUAL_MONTHS,
      termDiscounts.annual_discount_percent,
    ),
  };
}
