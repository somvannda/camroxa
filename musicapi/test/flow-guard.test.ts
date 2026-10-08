import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Regression guard for the generation-flow guard: derivative endpoints must
// reference an owned, completed asset. The guard is inert until
// `config.flowGuard.enforced` is turned on, so these assertions also pin the
// default-off rollout.

process.env.JWT_SECRET ??= "unit-test-jwt-secret-0123456789abcdef0123456789";
process.env.COOKIE_ENCRYPTION_KEY ??=
  "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

const source = readFileSync(new URL("../src/server.ts", import.meta.url), "utf8");
const configSource = readFileSync(new URL("../src/config.ts", import.meta.url), "utf8");
const runtimeSource = readFileSync(new URL("../src/runtimeSettings.ts", import.meta.url), "utf8");

const { config } = await import("../src/config.js");

test("flow guard is configured and defaults to off", () => {
  assert.equal(typeof config.flowGuard.enforced, "boolean");
  if (process.env.FLOW_GUARD_ENFORCED === undefined) {
    assert.equal(config.flowGuard.enforced, false, "the flow guard must default to off");
  }
  assert.match(configSource, /flowGuard:\s*\{[\s\S]*?enforced:/, "config.flowGuard is missing");
  assert.match(runtimeSource, /FLOW_GUARD_ENFORCED/, "the admin setting must expose FLOW_GUARD_ENFORCED");
  assert.match(runtimeSource, /Generation flow guard/, "the admin group label is missing");
});

test("the flow-guard helpers are defined", () => {
  assert.match(source, /async function findAssetOwner\(/, "findAssetOwner is missing");
  assert.match(source, /async function assetProducedByCompletedJob\(/, "assetProducedByCompletedJob is missing");
  assert.match(source, /async function requireOwnedAsset\(/, "requireOwnedAsset is missing");
  assert.match(source, /async function enforceFlow\(/, "enforceFlow is missing");
  assert.match(source, /function denyFlow\(/, "denyFlow is missing");
});

test("the shared route factories enforce the prerequisite asset", () => {
  for (const factory of ["meClipRoute", "meResultRoute", "clipRoute"]) {
    assert.match(
      source,
      new RegExp(`function ${factory}\\([\\s\\S]{0,2500}?requireOwnedAsset\\(`),
      `${factory} must call requireOwnedAsset`,
    );
  }
});

test("no deny-foreign-only check remains (all upgraded to the positive guard)", () => {
  assert.doesNotMatch(
    source,
    /assetOwnedByOtherUser/,
    "an old deny-foreign-only ownership check still exists",
  );
});
