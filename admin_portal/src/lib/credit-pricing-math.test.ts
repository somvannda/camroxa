import { describe, expect, it } from 'vitest';

import { computeMargins, marginFromPricing, pricingFromMargin } from './credit-pricing-math';

describe('credit-pricing-math', () => {
  it('computes markup on cost above 100%', () => {
    const margins = computeMargins(0.0048, 0.0016, 0.01);
    expect(margins.profitPercentOnCost).toBe(200);
    expect(margins.chargeMultiplier).toBe(3);
    expect(margins.profitPercentOnRevenue).toBeCloseTo(66.67, 2);
  });

  it('1000% margin charges 11x cost', () => {
    const margins = computeMargins(0.0176, 0.0016, 0.01);
    expect(margins.profitPercentOnCost).toBe(1000);
    expect(margins.chargeMultiplier).toBe(11);
    expect(margins.profitDollars).toBeCloseTo(0.00016, 8);
  });

  it('supports very large markup for tiny costs', () => {
    const pricing = pricingFromMargin(0.0016, 20_000_000);
    expect(pricing).toBe(320.0016);
    expect(marginFromPricing(0.0016, pricing)).toBe(20_000_000);
    const margins = computeMargins(pricing, 0.0016, 0.01);
    expect(margins.profitPercentOnCost).toBe(20_000_000);
    expect(margins.profitPercentOnRevenue).toBeCloseTo(100, 2);
  });
});
