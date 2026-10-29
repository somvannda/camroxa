import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  CREATE_COOLDOWN_MS,
  CREATE_MAX_QUEUE_FREE,
  CREATE_MAX_QUEUE_PAID,
  cooldownMsForAttempt,
  createActionDisabled,
  createActionLabel,
  parseRetryAfterSeconds,
  queueLimitForUser,
  remainingSeconds,
} from './create-submit-queue.ts';

describe('create-submit-queue', () => {
  it('parses Retry-After seconds', () => {
    assert.equal(parseRetryAfterSeconds('8'), 8);
    assert.equal(parseRetryAfterSeconds(null), null);
  });

  it('uses a 5 second cooldown', () => {
    assert.equal(CREATE_COOLDOWN_MS, 5_000);
    assert.equal(cooldownMsForAttempt(null), 5_000);
    assert.equal(cooldownMsForAttempt(20), 20_000);
  });

  it('caps every user at 20 (packs-only: credits are the gate)', () => {
    assert.equal(queueLimitForUser(true), CREATE_MAX_QUEUE_PAID);
    assert.equal(queueLimitForUser(false), CREATE_MAX_QUEUE_FREE);
    assert.equal(CREATE_MAX_QUEUE_PAID, 20);
    assert.equal(CREATE_MAX_QUEUE_FREE, 20);
  });

  it('keeps Create disabled for 5 seconds after a click', () => {
    assert.equal(
      createActionDisabled({
        formReady: true,
        needsUpgrade: false,
        hardLocked: false,
        busy: false,
        coolingDown: true,
        queueUsed: 0,
        queueLimit: 20,
      }),
      true,
    );
    assert.equal(
      createActionLabel({
        busy: false,
        hardLocked: false,
        coolingDown: true,
        cooldownSeconds: 4,
        queueUsed: 1,
        queueLimit: 20,
      }),
      'Wait 4s',
    );
  });

  it('blocks when the server queue is full', () => {
    assert.equal(
      createActionDisabled({
        formReady: true,
        needsUpgrade: false,
        hardLocked: false,
        busy: false,
        coolingDown: false,
        queueUsed: 2,
        queueLimit: 2,
      }),
      true,
    );
  });

  it('counts remaining cooldown seconds', () => {
    assert.equal(remainingSeconds(1_000, 250), 1);
    assert.equal(remainingSeconds(1_000, 1_000), 0);
  });
});
