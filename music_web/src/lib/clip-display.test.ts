import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { formatGeneratedTime, formatModelVersionTag } from './clip-display.ts';

const PHNOM_PENH = 'Asia/Phnom_Penh';
const NOW = new Date('2026-08-26T09:00:00.000Z');

describe('formatModelVersionTag', () => {
  it('maps V5_5 and dotted aliases to v5.5', () => {
    assert.equal(formatModelVersionTag('V5_5'), 'v5.5');
    assert.equal(formatModelVersionTag('v5.5'), 'v5.5');
    assert.equal(formatModelVersionTag(null), 'v5.5');
  });

  it('maps other models to v5', () => {
    assert.equal(formatModelVersionTag('V5'), 'v5');
    assert.equal(formatModelVersionTag('v4'), 'v5');
  });
});

describe('formatGeneratedTime', () => {
  it('returns empty for missing or invalid values', () => {
    assert.equal(formatGeneratedTime(null), '');
    assert.equal(formatGeneratedTime(''), '');
    assert.equal(formatGeneratedTime('not-a-date'), '');
  });

  it('shows clock time for the same local day', () => {
    assert.equal(
      formatGeneratedTime('2026-08-26T03:30:00.000Z', {
        now: NOW,
        locale: 'en-US',
        timeZone: PHNOM_PENH,
      }),
      '10:30 AM',
    );
  });

  it('includes the date when the clip is from another day', () => {
    assert.equal(
      formatGeneratedTime('2026-08-25T03:30:00.000Z', {
        now: NOW,
        locale: 'en-US',
        timeZone: PHNOM_PENH,
      }),
      'Aug 25 · 10:30 AM',
    );
  });

  it('includes the year when the clip is from another year', () => {
    assert.equal(
      formatGeneratedTime('2025-12-31T03:30:00.000Z', {
        now: NOW,
        locale: 'en-US',
        timeZone: PHNOM_PENH,
      }),
      'Dec 31, 2025 · 10:30 AM',
    );
  });
});
