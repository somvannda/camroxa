import { test } from "node:test";
import assert from "node:assert/strict";
import { trustProxyOption } from "../src/trustProxy.js";

// Locks in the anti-spoof default: `TRUST_PROXY` must be off unless an operator
// explicitly opts in, otherwise a caller can forge `X-Forwarded-For` to defeat
// an API key's `ip_whitelist`.
test("trustProxy defaults to off", () => {
  assert.equal(trustProxyOption({}), false);
  assert.equal(trustProxyOption({ TRUST_PROXY: "" }), false);
  assert.equal(trustProxyOption({ TRUST_PROXY: "false" }), false);
  assert.equal(trustProxyOption({ TRUST_PROXY: "0" }), false);
});

test("trustProxy accepts true and proxy hop counts", () => {
  assert.equal(trustProxyOption({ TRUST_PROXY: "true" }), true);
  assert.equal(trustProxyOption({ TRUST_PROXY: "2" }), 2);
});

test("trustProxy accepts an address/CIDR allowlist", () => {
  assert.deepEqual(trustProxyOption({ TRUST_PROXY: "127.0.0.1" }), ["127.0.0.1"]);
  assert.deepEqual(trustProxyOption({ TRUST_PROXY: "10.0.0.0/8, 127.0.0.1" }), [
    "10.0.0.0/8",
    "127.0.0.1",
  ]);
});
