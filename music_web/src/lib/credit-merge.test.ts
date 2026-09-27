import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { splitCreditBalance } from './credit-merge.ts';

describe('splitCreditBalance', () => {
  it('splits a free daily grant from the live balance, not the stale lot', () => {
    // The wallet holds 30 of a 50/day grant; the lot still reports 50 granted.
    assert.deepEqual(splitCreditBalance(30, 50, 0), {
      dailyFree: 30,
      monthlyPool: 0,
      monthlyRemaining: 0,
      monthlyUsed: 0,
      topup: 0,
    });
  });

  it('derives monthly usage from the balance instead of the stale grant lot', () => {
    // 100/month plan with 60 credits left => 40 used.
    assert.deepEqual(splitCreditBalance(60, 0, 100), {
      dailyFree: 0,
      monthlyPool: 100,
      monthlyRemaining: 60,
      monthlyUsed: 40,
      topup: 0,
    });
  });

  it('treats the balance above the monthly pool as top-up credits', () => {
    assert.deepEqual(splitCreditBalance(300, 0, 100), {
      dailyFree: 0,
      monthlyPool: 100,
      monthlyRemaining: 100,
      monthlyUsed: 0,
      topup: 200,
    });
  });

  it('spends the expiring daily grant before the monthly pool', () => {
    assert.deepEqual(splitCreditBalance(105, 10, 100), {
      dailyFree: 10,
      monthlyPool: 100,
      monthlyRemaining: 95,
      monthlyUsed: 5,
      topup: 0,
    });
  });

  it('never reports negative remaining credits when the balance is empty', () => {
    assert.deepEqual(splitCreditBalance(0, 0, 100), {
      dailyFree: 0,
      monthlyPool: 100,
      monthlyRemaining: 0,
      monthlyUsed: 100,
      topup: 0,
    });
  });

  it('falls back to the v2 pools when the v3 plan is missing', () => {
    assert.deepEqual(splitCreditBalance(15, 20, 100), {
      dailyFree: 15,
      monthlyPool: 100,
      monthlyRemaining: 0,
      monthlyUsed: 100,
      topup: 0,
    });
  });

  it('clamps a negative balance instead of returning negative credits', () => {
    assert.deepEqual(splitCreditBalance(-5, 50, 100), {
      dailyFree: 0,
      monthlyPool: 100,
      monthlyRemaining: 0,
      monthlyUsed: 100,
      topup: 0,
    });
  });
});
