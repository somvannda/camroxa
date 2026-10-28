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

test("the sunoapi.org alias handlers run the guard", () => {
  assert.match(
    source,
    /assetIdsInBody\(in_\)/,
    "the /api/v1 compatibility handlers must run the flow check on their body",
  );
});

test("no deny-foreign-only check remains (all upgraded to the positive guard)", () => {
  assert.doesNotMatch(
    source,
    /assetOwnedByOtherUser/,
    "an old deny-foreign-only ownership check still exists",
  );
});

// --- coverage: every top-level job-creating route that reads a clip id must
// guard it. Factory routes (variable path) are covered by the factory test above.

interface Route {
  method: string;
  path: string;
  body: string;
}

/** Extract `app.<method>(<first-string-literal>, …<balanced body>)` registrations. */
function routeRegistrations(): Route[] {
  const re = /\bapp\.(get|post|put|patch|delete|all)\s*\(/g;
  const routes: Route[] = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(source)) !== null) {
    let i = re.lastIndex;
    let depth = 1;
    let inStr: string | null = null;
    let body = "";
    while (i < source.length && depth > 0 && body.length < 12000) {
      const c = source[i];
      if (inStr) {
        if (c === "\\") {
          body += c;
          i++;
          if (i < source.length) body += source[i];
          i++;
          continue;
        }
        if (c === inStr) inStr = null;
        body += c;
        i++;
        continue;
      }
      if (c === '"' || c === "'" || c === "`") {
        inStr = c;
        body += c;
        i++;
        continue;
      }
      if (c === "(") depth++;
      else if (c === ")") {
        depth--;
        if (depth === 0) break;
      }
      body += c;
      i++;
    }
    const pathMatch = body.match(/^\s*(?:\(\s*)?["'`]([^"'`]+)["'`]/);
    if (pathMatch) {
      routes.push({
        method: m[1].toUpperCase(),
        path: pathMatch[1].replace(/\$\{PREFIX\}/g, "/api/v1"),
        body,
      });
    }
  }
  return routes;
}

const CLIP_READ = /\b(clip_id|clipId|clip_ids|clipIds|audioId|audio_id|uploaded_clip_id|uploadedClipId)\b/;
// Internal studio routes are token-authenticated and resolve the clip's
// recorded asset owner before creating a job; that lookup is their ownership
// guard because no end-user id is present on the internal call.
const GUARD = /enforceFlow\(|requireOwnedAsset\(|assetIdsInBody\(|findAssetAccountAny\(/;

test("every job-creating route that reads a clip id enforces the flow guard", () => {
  const offenders = routeRegistrations()
    .filter((r) => CLIP_READ.test(r.body) && /\bnewJob\(/.test(r.body))
    .filter((r) => !GUARD.test(r.body))
    .map((r) => `${r.method} ${r.path}`);
  assert.deepEqual(
    offenders,
    [],
    `job-creating routes that read a clip id without the flow guard: ${offenders.join(", ")}`,
  );
});
