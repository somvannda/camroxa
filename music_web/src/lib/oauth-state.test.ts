import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { desktopHandoffPort, desktopHandoffUrl } from './oauth-state.ts';

/** Build a JWT-shaped state whose payload is `payload` (signature ignored). */
function stateWith(payload: Record<string, unknown>): string {
  const encode = (value: unknown) =>
    Buffer.from(JSON.stringify(value))
      .toString('base64')
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '');
  return `${encode({ alg: 'HS256' })}.${encode(payload)}.signature`;
}

describe('desktopHandoffPort', () => {
  it('reads the port from a desktop state', () => {
    const state = stateWith({ type: 'google_oauth_state', desktop_port: 41580 });
    assert.equal(desktopHandoffPort(state), 41580);
  });

  it('ignores browser states without a port', () => {
    const state = stateWith({ type: 'google_oauth_state' });
    assert.equal(desktopHandoffPort(state), null);
  });

  it('ignores missing, malformed and out-of-range states', () => {
    assert.equal(desktopHandoffPort(null), null);
    assert.equal(desktopHandoffPort(''), null);
    assert.equal(desktopHandoffPort('not-a-jwt'), null);
    assert.equal(desktopHandoffPort('a.@@@.c'), null);
    assert.equal(desktopHandoffPort(stateWith({ desktop_port: 0 })), null);
    assert.equal(desktopHandoffPort(stateWith({ desktop_port: 70000 })), null);
    assert.equal(desktopHandoffPort(stateWith({ desktop_port: 'abc' })), null);
  });
});

describe('desktopHandoffUrl', () => {
  it('targets the loopback listener with the code and state', () => {
    assert.equal(
      desktopHandoffUrl(41580, { code: 'abc 123', state: 's.t.s' }),
      'http://127.0.0.1:41580/google/callback?code=abc+123&state=s.t.s',
    );
  });

  it('relays a cancelled consent', () => {
    assert.equal(
      desktopHandoffUrl(41580, { error: 'access_denied' }),
      'http://127.0.0.1:41580/google/callback?error=access_denied',
    );
  });

  it('never produces a non-loopback host', () => {
    assert.ok(desktopHandoffUrl(41580, { code: 'x' }).startsWith('http://127.0.0.1:41580/'));
  });
});
