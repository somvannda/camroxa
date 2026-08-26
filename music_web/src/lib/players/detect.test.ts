import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { detectPlayer } from './detect.ts';

describe('detectPlayer', () => {
  it('maps iOS Chrome (CriOS) to ios-chrome', () => {
    assert.equal(
      detectPlayer({
        userAgent:
          'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/129.0.6668.69 Mobile/15E148 Safari/604.1',
      }),
      'ios-chrome',
    );
  });

  it('maps Windows Chrome to win-chrome', () => {
    assert.equal(
      detectPlayer({
        userAgent:
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
        platform: 'Win32',
      }),
      'win-chrome',
    );
  });

  it('maps macOS Chrome to macos-chrome, not win-chrome', () => {
    assert.equal(
      detectPlayer({
        userAgent:
          'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
        platform: 'MacIntel',
        maxTouchPoints: 0,
      }),
      'macos-chrome',
    );
  });

  it('maps macOS Safari to macos-safari', () => {
    assert.equal(
      detectPlayer({
        userAgent:
          'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15',
        platform: 'MacIntel',
        maxTouchPoints: 0,
        vendor: 'Apple Computer, Inc.',
      }),
      'macos-safari',
    );
  });

  it('maps Safari iPhone to ios-safari', () => {
    assert.equal(
      detectPlayer({
        userAgent:
          'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1',
      }),
      'ios-safari',
    );
  });

  it('maps FxiOS to ios-firefox', () => {
    assert.equal(
      detectPlayer({
        userAgent:
          'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/129.0 Mobile/15E148 Safari/605.1.15',
      }),
      'ios-firefox',
    );
  });

  it('maps Windows Edge to win-edge', () => {
    assert.equal(
      detectPlayer({
        userAgent:
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0',
        platform: 'Win32',
      }),
      'win-edge',
    );
  });

  it('maps Android Chrome to android-chrome', () => {
    assert.equal(
      detectPlayer({
        userAgent:
          'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36',
      }),
      'android-chrome',
    );
  });

  it('does not call Linux Chrome win-chrome', () => {
    assert.equal(
      detectPlayer({
        userAgent:
          'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
        platform: 'Linux x86_64',
      }),
      'default',
    );
  });
});
