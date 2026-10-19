import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { isFailedStatus, TERMINAL_FAILURE_STATUSES } from './generation-status.ts';

describe('isFailedStatus', () => {
  it('treats every Suno failure status as failed, case-insensitively', () => {
    for (const status of TERMINAL_FAILURE_STATUSES) {
      assert.equal(isFailedStatus(status), true, status);
      assert.equal(isFailedStatus(status.toLowerCase()), true, status.toLowerCase());
    }
  });

  it('does not treat a successful or in-flight song as failed', () => {
    for (const status of ['SUCCESS', 'PENDING', 'RUNNING', 'QUEUED', 'PROCESSING', '']) {
      assert.equal(isFailedStatus(status), false, status || '(empty)');
    }
    assert.equal(isFailedStatus(null), false);
    assert.equal(isFailedStatus(undefined), false);
  });

  it('trims surrounding whitespace', () => {
    assert.equal(isFailedStatus('  rejected '), true);
  });
});
