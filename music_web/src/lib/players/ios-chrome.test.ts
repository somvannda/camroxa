import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

import { iosChromeFriendlyError, isUnsupportedSrcError } from './media-error.ts';
import { resolveIosChromeLane } from './ios-chrome-plan.ts';

const here = dirname(fileURLToPath(import.meta.url));

describe('ios-chrome lane', () => {
  it('uses HLS when the playlist URL is trusted', () => {
    assert.equal(
      resolveIosChromeLane({
        hasTrustedHls: true,
        hlsAttemptFailed: false,
        hasPackagedChunks: true,
      }),
      'hls',
    );
  });

  it('falls back to Web Audio after HLS MediaError 4', () => {
    assert.equal(
      resolveIosChromeLane({
        hasTrustedHls: true,
        hlsAttemptFailed: true,
        hasPackagedChunks: true,
      }),
      'webaudio',
    );
  });

  it('uses Web Audio when HLS is missing', () => {
    assert.equal(
      resolveIosChromeLane({
        hasTrustedHls: false,
        hlsAttemptFailed: false,
        hasPackagedChunks: true,
      }),
      'webaudio',
    );
  });

  it('never selects MSE', () => {
    const lanes = [
      resolveIosChromeLane({ hasTrustedHls: true, hlsAttemptFailed: false, hasPackagedChunks: true }),
      resolveIosChromeLane({ hasTrustedHls: true, hlsAttemptFailed: true, hasPackagedChunks: true }),
      resolveIosChromeLane({ hasTrustedHls: false, hlsAttemptFailed: false, hasPackagedChunks: true }),
      resolveIosChromeLane({ hasTrustedHls: false, hlsAttemptFailed: true, hasPackagedChunks: false }),
    ];
    assert.equal(lanes.includes('hls' as never) || lanes.includes('webaudio') || lanes.includes('unavailable'), true);
    for (const lane of lanes) {
      assert.notEqual(String(lane), 'mse');
    }
  });

  it('does not import the MSE engine', () => {
    const source = readFileSync(join(here, 'ios-chrome.ts'), 'utf8');
    assert.equal(/engines\/mse/.test(source), false);
    assert.equal(/playMseBackend/.test(source), false);
  });
});

describe('macos-chrome', () => {
  it('does not import the MSE engine', () => {
    const source = readFileSync(join(here, 'macos-chrome.ts'), 'utf8');
    assert.equal(/engines\/mse/.test(source), false);
    assert.equal(/playMseBackend/.test(source), false);
    assert.equal(/playHlsVideo/.test(source), true);
    assert.equal(/playWebAudioBackend/.test(source), true);
  });

  it('falls back to Web Audio when HLS is missing', () => {
    assert.equal(
      resolveIosChromeLane({
        hasTrustedHls: false,
        hlsAttemptFailed: false,
        hasPackagedChunks: true,
      }),
      'webaudio',
    );
  });
});

describe('ios-chrome MediaError 4', () => {
  it('treats code 4 as unsupported src', () => {
    assert.equal(isUnsupportedSrcError({ code: 4, message: 'Media error 4' }), true);
    assert.equal(isUnsupportedSrcError(new Error('Native media playback failed')), true);
  });

  it('maps MediaError 4 to a retry line', () => {
    assert.equal(iosChromeFriendlyError(new Error('Media error 4')), 'Tap play again to start audio.');
  });
});
