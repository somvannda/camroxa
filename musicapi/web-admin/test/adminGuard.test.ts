import { test } from "node:test";
import assert from "node:assert/strict";
import { probeAdminSession, SESSION_COOKIE } from "../lib/adminGuard.ts";

const BACKEND = "http://127.0.0.1:4003";

/** A fetch double that records the request and returns a canned response. */
function fakeFetch(status: number, body: unknown = {}) {
  const calls: Array<{ url: string; init: RequestInit | undefined }> = [];
  const impl = (async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ url: String(input), init });
    return new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    });
  }) as typeof fetch;
  return { impl, calls };
}

/** A fetch double that rejects, simulating an unreachable API/timeout. */
function failingFetch() {
  const impl = (async () => {
    throw new Error("ECONNREFUSED");
  }) as typeof fetch;
  return impl;
}

test("forwards the admin cookie to the API's /auth/me", async () => {
  const { impl, calls } = fakeFetch(200, { role: "admin", status: "active" });
  await probeAdminSession("tok-123", BACKEND, impl);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, `${BACKEND}/auth/me`);
  const headers = calls[0].init?.headers as Record<string, string>;
  assert.equal(headers.cookie, `${SESSION_COOKIE}=tok-123`);
});

test("active admin session is allowed", async () => {
  const { impl } = fakeFetch(200, { role: "admin", status: "active" });
  const probe = await probeAdminSession("tok", BACKEND, impl);
  assert.equal(probe.kind, "active");
});

test("a non-admin session is inactive", async () => {
  const { impl } = fakeFetch(200, { role: "user", status: "active" });
  const probe = await probeAdminSession("tok", BACKEND, impl);
  assert.equal(probe.kind, "inactive");
});

test("a suspended admin session is inactive", async () => {
  const { impl } = fakeFetch(200, { role: "admin", status: "suspended" });
  const probe = await probeAdminSession("tok", BACKEND, impl);
  assert.equal(probe.kind, "inactive");
});

test("401/403 means the session is dead (cookie may be cleared)", async () => {
  for (const status of [401, 403]) {
    const { impl } = fakeFetch(status, { error: "Unauthorized." });
    const probe = await probeAdminSession("tok", BACKEND, impl);
    assert.equal(probe.kind, "dead", `status ${status} should be dead`);
  }
});

test("a 5xx must NOT be treated as a dead session", async () => {
  for (const status of [500, 502, 503]) {
    const { impl } = fakeFetch(status, { error: "boom" });
    const probe = await probeAdminSession("tok", BACKEND, impl);
    assert.equal(probe.kind, "unavailable", `status ${status} should be unavailable`);
  }
});

test("an unreachable API is unavailable, not dead", async () => {
  const probe = await probeAdminSession("tok", BACKEND, failingFetch());
  assert.equal(probe.kind, "unavailable");
});

test("a 429 is unavailable, not dead", async () => {
  const { impl } = fakeFetch(429, { error: "rate limited" });
  const probe = await probeAdminSession("tok", BACKEND, impl);
  assert.equal(probe.kind, "unavailable");
});
