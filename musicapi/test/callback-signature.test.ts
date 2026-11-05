import assert from "node:assert/strict";
import test from "node:test";

import { callbackSignatureHeaders } from "../src/callbackSignature.js";

test("no secret keeps callbacks unsigned", () => {
  assert.deepEqual(callbackSignatureHeaders("", "{}"), {});
  assert.deepEqual(callbackSignatureHeaders("   ", "{}"), {});
});

test("signs the exact body with sha256= hex", () => {
  const headers = callbackSignatureHeaders("shared-secret", '{"a":1}');
  assert.equal(
    headers["X-Signature"],
    "sha256=0294f2251135bb0b0299c77d61cf05370fad18c7d5bc9dea04d2b4d415277ada",
  );
});

test("body or secret changes the signature", () => {
  const a = callbackSignatureHeaders("s", '{"a":1}')["X-Signature"];
  const b = callbackSignatureHeaders("s", '{"a":2}')["X-Signature"];
  const c = callbackSignatureHeaders("t", '{"a":1}')["X-Signature"];
  assert.notEqual(a, b);
  assert.notEqual(a, c);
});

test("trims the configured secret", () => {
  assert.deepEqual(
    callbackSignatureHeaders("  s  ", "{}"),
    callbackSignatureHeaders("s", "{}"),
  );
});
