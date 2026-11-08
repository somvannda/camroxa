import assert from 'node:assert/strict';
import { beforeEach, describe, it } from 'node:test';

import { musicAuthFetch, resetAuthRefreshState } from './auth-fetch.ts';

type RecordedCall = { url: string; method: string };

function stubFetch(
  handler: (url: string, init: RequestInit) => Promise<Response>,
): RecordedCall[] {
  const calls: RecordedCall[] = [];
  (globalThis as { fetch: typeof fetch }).fetch = (async (
    input: string | URL | Request,
    init: RequestInit = {},
  ) => {
    const url = String(input);
    calls.push({ url, method: String(init.method ?? 'GET') });
    return handler(url, init);
  }) as typeof fetch;
  return calls;
}

function response(status: number): Response {
  return new Response('{}', {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function refreshCalls(calls: RecordedCall[]): number {
  return calls.filter((call) => call.url.endsWith('/api/v3/auth/refresh')).length;
}

describe('musicAuthFetch refresh backoff', () => {
  beforeEach(() => {
    resetAuthRefreshState();
  });

  it('does not re-attempt a rejected refresh on every poll', async () => {
    const calls = stubFetch(async () => response(401));

    const first = await musicAuthFetch('/api/v3/web-music/licenses/client-trace', {
      method: 'POST',
      body: '{}',
    });
    const second = await musicAuthFetch('/api/v3/web-music/licenses/client-trace', {
      method: 'POST',
      body: '{}',
    });

    assert.equal(first.status, 401);
    assert.equal(second.status, 401);
    assert.equal(refreshCalls(calls), 1);
  });

  it('retries the original request after a successful refresh', async () => {
    let protectedCalls = 0;
    const calls = stubFetch(async (url) => {
      if (url.endsWith('/api/v3/auth/refresh')) {
        return response(200);
      }
      protectedCalls += 1;
      return protectedCalls === 1 ? response(401) : response(200);
    });

    const result = await musicAuthFetch('/api/v3/me/credits');

    assert.equal(result.status, 200);
    assert.equal(protectedCalls, 2);
    assert.equal(refreshCalls(calls), 1);
  });

  it('does not back off after a network failure, so a real login is picked up', async () => {
    let attempts = 0;
    stubFetch(async (url) => {
      if (url.endsWith('/api/v3/auth/refresh')) {
        attempts += 1;
        throw new Error('offline');
      }
      return response(401);
    });

    await musicAuthFetch('/api/v3/web-music/licenses/heartbeat', { method: 'POST' });
    await musicAuthFetch('/api/v3/web-music/licenses/heartbeat', { method: 'POST' });

    assert.equal(attempts, 2);
  });

  it('never refreshes the refresh endpoint itself', async () => {
    const calls = stubFetch(async () => response(401));

    await musicAuthFetch('/api/v3/auth/refresh', { method: 'POST', body: '{}' });

    // Only the original call: the refresh endpoint must not trigger another refresh.
    assert.equal(calls.length, 1);
  });
});
