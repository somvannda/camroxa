import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Regression guard for the customer credit gate. Free (0-cost) generation
// endpoints normally require a funded account so "free" stays a perk for paying
// customers — the deliberate exception is the monthly free allowance, which can
// only pay for its configured model (V6-Mini) and never for V6 / V6-WILD.
// Purchased credits stay universal, premium rejections return a buy-a-pack
// upsell, and read/detail/download routes stay usable by a drained customer.

process.env.JWT_SECRET ??= "unit-test-jwt-secret-0123456789abcdef0123456789";
process.env.COOKIE_ENCRYPTION_KEY ??=
  "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

const source = readFileSync(new URL("../src/server.ts", import.meta.url), "utf8");
const configSource = readFileSync(new URL("../src/config.ts", import.meta.url), "utf8");
const modelsSource = readFileSync(new URL("../src/models.ts", import.meta.url), "utf8");
const noCarryMigration = readFileSync(
  new URL("../migrations/0036_allowance_no_carryover.sql", import.meta.url),
  "utf8",
);

const { config } = await import("../src/config.js");
const { INTEGRATION_GROUPS } = await import("../src/runtimeSettings.js");

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

test("the monthly free allowance deliberately bypasses the funded floor", () => {
  // The allowance must be an explicit, admin-configurable exception — not an
  // accidental hole in the gate above. It pays for V6-Mini only and never for
  // a premium model.
  assert.match(
    source,
    /isAllowanceModel\(model, config\.freeMonthly\)/,
    "the allowance-model check is missing",
  );
  assert.match(source, /async function ensureAllowance\(/, "the lazy monthly grant is missing");
  assert.match(source, /async function consumeAllowance\(/, "the atomic allowance spend is missing");
  assert.match(source, /async function refundAllowance\(/, "allowance refunds are missing");
  assert.match(source, /monthly_allowances/, "the monthly allowance table is not used");
  assert.match(
    source,
    /freeModelRoutingPolicy\(config\.freeMonthly\.allowPaidFallback\)/,
    "V6-Mini must route through the free-model policy",
  );
  assert.match(
    modelsSource,
    /return allowPaidFallback \? "prefer_free" : "free_only"/,
    "V6-Mini must default to free Suno accounts only",
  );
  assert.match(
    source,
    /canSpendAllowance\(model, config\.freeMonthly, universal\)/,
    "the allowance must be model-scoped until a purchase unlocks it",
  );
  assert.match(
    source,
    /allowanceUniversal\(/,
    "the purchase-unlocks-allowance rule is missing",
  );
  assert.match(source, /credit_pack_required/, "premium models must return the buy-a-pack upsell");
  assert.match(source, /allowance_remaining/, "the upsell must expose the remaining allowance");
  assert.match(
    configSource,
    /freeMonthly:\s*\{[\s\S]*?credits:/,
    "config.freeMonthly.credits is missing",
  );
});

test("the monthly free allowance is editable from the admin settings console", () => {
  const group = INTEGRATION_GROUPS.find((g) => g.key === "freeMonthly");
  assert.ok(group, "the Free monthly settings group is missing");
  assert.deepEqual(
    group.fields.map((f) => f.key).sort(),
    ["allowPaidFallback", "credits", "enabled", "model"],
    "free-monthly fields changed without updating the admin contract",
  );
});

test("the allowance never carries unused credits into the next month", () => {
  // Charging reads only the current period's row, so unused credits are not
  // added to the next grant. A free user's balance is capped at one grant.
  assert.match(
    source,
    /FROM monthly_allowances WHERE user_id = \$1 AND period_start = \$2::date/,
    "the allowance lookup must be scoped to the current period",
  );
  assert.doesNotMatch(
    source,
    /SUM\s*\(\s*(granted|used)\s*\)[\s\S]{0,80}monthly_allowances/i,
    "the allowance must never be aggregated across periods",
  );
  assert.match(
    noCarryMigration,
    /CHECK \(used <= granted\)/,
    "the used <= granted constraint is missing",
  );
});
