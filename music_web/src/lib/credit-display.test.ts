import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { cardBulletsForPlan, creditResetLabel } from './credit-display.ts';

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
