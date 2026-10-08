import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Regression guard for the customer credit gate: free (0-cost) generation
// endpoints must require a funded account so "free" is a perk for paying
// customers instead of an open tier for every signed-in user. Paid endpoints
// keep their per-cost gate, and read/detail/download routes stay usable by a
// drained customer.

process.env.JWT_SECRET ??= "unit-test-jwt-secret-0123456789abcdef0123456789";
process.env.COOKIE_ENCRYPTION_KEY ??=
  "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

const source = readFileSync(new URL("../src/server.ts", import.meta.url), "utf8");
const configSource = readFileSync(new URL("../src/config.ts", import.meta.url), "utf8");

const { config } = await import("../src/config.js");

test("creditGate.minCredits is configured (default 10)", () => {
  assert.equal(typeof config.creditGate.minCredits, "number");
  assert.ok(config.creditGate.minCredits >= 0, "minCredits must be non-negative");
  if (process.env.USER_MIN_CREDITS === undefined) {
    assert.equal(config.creditGate.minCredits, 10, "default floor should be 10 credits");
  }
});

test("the funded-account gate is defined and wired into both charge paths", () => {
  assert.match(
    configSource,
    /creditGate:\s*\{[\s\S]*?minCredits:/,
    "config.creditGate.minCredits is missing",
  );
  assert.match(source, /async function requireFundedAccount\(/, "requireFundedAccount is missing");
  assert.match(
    source,
    /async function charge\(key: DbApiKey, amount: number\): Promise<boolean> \{[\s\S]{0,600}?if \(amount <= 0\) return requireFundedAccount\(key\.user_id\);/,
    "charge() must gate 0-cost endpoints on a funded account",
  );
  assert.match(
    source,
    /async function chargeUserKey\([\s\S]{0,600}?if \(amount <= 0\) \{[\s\S]{0,800}?requireFundedAccount\(userId\)/,
    "chargeUserKey() must gate 0-cost endpoints on a funded account",
  );
});

test("read/detail/download routes use the non-gating chargeRead variant", () => {
  assert.match(source, /async function chargeRead\(/, "chargeRead is missing");
  // The /v1 *_detail reads (via the detailRoute factory) must use chargeRead.
  assert.match(
    source,
    /function detailRoute\([\s\S]{0,2000}?await chargeRead\(key, cost\)/,
    "detailRoute must use chargeRead so a drained customer can still read details",
  );
  // Timestamped-lyrics reads on /v1 and its aliases must use chargeRead.
  assert.match(
    source,
    /costFor\("timestamped_lyrics_detail"\);\s*if \(!\(await chargeRead\(key, cost\)\)\)/,
    "timestamped-lyrics reads must use chargeRead",
  );
  // WAV conversion/delivery on /v1 is a read of an owned clip.
  assert.match(
    source,
    /costFor\("wav"\);\s*if \(!\(await chargeRead\(key, cost\)\)\)/,
    "WAV delivery routes must use chargeRead",
  );
  // The /me read guards must stay open for 0-cost (`cost > 0 && key === null`).
  assert.match(
    source,
    /if \(cost > 0 && key === null\)/,
    "expected the open read guard `cost > 0 && key === null`",
  );
});

test("free generation guards reject on a missing key, not only on positive cost", () => {
  // The old `if (cost > 0 && !key)` guard silently let 0-cost generation run.
  assert.doesNotMatch(
    source,
    /if \(cost > 0 && !key\)/,
    "a free generation guard still uses the bypassing `cost > 0 && !key` form",
  );
  // The user-facing message must be exactly "Insufficient credits.".
  assert.doesNotMatch(
    source,
    /Add credits to an API key first/,
    "an old verbose insufficient-credits message is still present",
  );
});
