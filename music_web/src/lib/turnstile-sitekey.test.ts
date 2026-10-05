import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  SANDBOX_TURNSTILE_SITE_KEY,
  isSandboxTurnstileSiteKey,
  resolveTurnstileSiteKey,
} from './turnstile-sitekey.ts';

describe('resolveTurnstileSiteKey', () => {
  it('uses the configured key as-is', () => {
    assert.equal(resolveTurnstileSiteKey('0xPRODUCTION', 'production'), '0xPRODUCTION');
  });

  it('trims surrounding whitespace', () => {
    assert.equal(resolveTurnstileSiteKey('  0xPRODUCTION  ', 'production'), '0xPRODUCTION');
  });

  it('falls back to the sandbox key only in development', () => {
    assert.equal(resolveTurnstileSiteKey('', 'development'), SANDBOX_TURNSTILE_SITE_KEY);
    assert.equal(resolveTurnstileSiteKey(undefined, 'development'), SANDBOX_TURNSTILE_SITE_KEY);
    assert.equal(resolveTurnstileSiteKey(null, 'development'), SANDBOX_TURNSTILE_SITE_KEY);
  });

  it('stays empty in production when unset (no silent sandbox fallback)', () => {
    // Regression: the old component defaulted to the sandbox key here, which
    // Cloudflare rejects on music.camxora.com and disabled every login.
    assert.equal(resolveTurnstileSiteKey('', 'production'), '');
    assert.equal(resolveTurnstileSiteKey(undefined, 'production'), '');
    assert.equal(resolveTurnstileSiteKey('   ', 'production'), '');
  });

  it('treats an unknown NODE_ENV as production-safe', () => {
    assert.equal(resolveTurnstileSiteKey(undefined, undefined), '');
    assert.equal(resolveTurnstileSiteKey(undefined, 'test'), '');
  });
});

describe('isSandboxTurnstileSiteKey', () => {
  it('recognises the sandbox key, ignoring whitespace', () => {
    assert.equal(isSandboxTurnstileSiteKey(SANDBOX_TURNSTILE_SITE_KEY), true);
    assert.equal(isSandboxTurnstileSiteKey(` ${SANDBOX_TURNSTILE_SITE_KEY} `), true);
  });

  it('rejects anything else', () => {
    assert.equal(isSandboxTurnstileSiteKey('0xPRODUCTION'), false);
    assert.equal(isSandboxTurnstileSiteKey(''), false);
    assert.equal(isSandboxTurnstileSiteKey(undefined), false);
    assert.equal(isSandboxTurnstileSiteKey(null), false);
  });
});
