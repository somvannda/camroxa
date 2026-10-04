import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  cardBulletsForPlan,
  computeCreditDisplay,
  creditResetLabel,
  type CreditDisplayInput,
} from './credit-display.ts';

function freeBalance(overrides: Partial<CreditDisplayInput> = {}): CreditDisplayInput {
  return {
    total_credits: 50,
    monthly_credits: 50,
    monthly_credits_used: 0,
    topup_credits: 0,
    daily_free_credits: 0,
    daily_free_limit: 0,
    has_subscription: false,
    ...overrides,
  };
}

describe('creditResetLabel', () => {
  it('hides the line when daily is 0 and monthly does not grant', () => {
    assert.equal(creditResetLabel({ daily_credits: 0, monthly_credits: 0 }), null);
  });

  it('says daily when daily grants', () => {
    assert.equal(
      creditResetLabel({ daily_credits: 50, monthly_credits: 0 }),
      'Credit reset daily',
    );
  });

  it('says monthly when monthly grants and daily is 0', () => {
    assert.equal(
      creditResetLabel({ daily_credits: 0, monthly_credits: 50 }),
      'Credit reset monthly',
    );
  });

  it('prefers daily when both are set', () => {
    assert.equal(
      creditResetLabel({ daily_credits: 50, monthly_credits: 50 }),
      'Credit reset daily',
    );
  });

  it('uses an API-provided label', () => {
    assert.equal(
      creditResetLabel({
        daily_credits: 0,
        monthly_credits: 0,
        reset_label: 'Credit reset monthly',
      }),
      'Credit reset monthly',
    );
  });
});

describe('cardBulletsForPlan', () => {
  it('falls back to monthly reset copy for Free monthly grants', () => {
    assert.deepEqual(
      cardBulletsForPlan({
        name: 'Free',
        price_cents: 0,
        daily_credits: 0,
        monthly_credits: 50,
      }),
      ['Web Create', 'Monthly credit reset', 'Top-up packs'],
    );
  });

  it('falls back to daily reset copy for Free daily grants', () => {
    assert.deepEqual(
      cardBulletsForPlan({
        name: 'Free',
        price_cents: 0,
        daily_credits: 50,
        monthly_credits: 0,
      }),
      ['Web Create', 'Daily credit reset', 'Top-up packs'],
    );
  });
});

describe('computeCreditDisplay', () => {
  it('shows the real wallet above the Free monthly pool instead of freezing at the pool', () => {
    // Regression: 170 spendable, 50/month Free plan. The old card clamped
    // `remaining` to the 50-credit pool and never moved as credits were spent.
    const display = computeCreditDisplay(
      freeBalance({ total_credits: 170, topup_credits: 120 }),
    );
    assert.equal(display.remaining, 170);
    assert.equal(display.limit, 170);
    assert.equal(display.isLow, false);
  });

  it('moves the free card down as the wallet is spent', () => {
    const before = computeCreditDisplay(freeBalance({ total_credits: 170, topup_credits: 120 }));
    const after = computeCreditDisplay(freeBalance({ total_credits: 155, topup_credits: 105 }));
    assert.ok(after.remaining < before.remaining);
    assert.equal(after.remaining, 155);
  });

  it('drains the bar against the allowance once the wallet is below it', () => {
    const display = computeCreditDisplay(
      freeBalance({
        total_credits: 30,
        monthly_credits: 0,
        daily_free_limit: 50,
        daily_free_credits: 30,
      }),
    );
    assert.equal(display.remaining, 30);
    assert.equal(display.limit, 50);
    assert.equal(display.progressPct, 60);
    assert.equal(display.resetLabel, 'Credit reset daily');
  });

  it('explains extra credits as top-up on the free card', () => {
    const display = computeCreditDisplay(freeBalance({ total_credits: 170, topup_credits: 120 }));
    assert.match(String(display.promoText), /120 top-up credits/);
  });

  it('keeps a subscription returning the total with a monthly capacity', () => {
    const display = computeCreditDisplay(
      freeBalance({
        has_subscription: true,
        total_credits: 700,
        monthly_credits: 1000,
        monthly_credits_used: 300,
      }),
    );
    assert.equal(display.remaining, 700);
    assert.equal(display.hasSubscription, true);
  });

  it('returns safe defaults when the balance is unavailable', () => {
    const display = computeCreditDisplay(null);
    assert.equal(display.remaining, 0);
    assert.equal(display.isLow, true);
    assert.equal(display.hasSubscription, false);
  });
});
