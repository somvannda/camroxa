import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Static regression guard for the "generation/credit endpoints must stay
// authenticated" contract. It has two jobs:
//   1. prove the runtime deny-by-default backstop is registered, and
//   2. fail if a *direct* `app.<method>` route under a protected prefix is
//      added without a `requireAuth`/`requireKey`/`requireAdmin` call.
//
// Routes registered through the factory helpers (`meClipRoute`, `recordInfoRoute`,
// `sunoAlias`, …) use a variable path and are covered by the runtime backstop
// instead; the factories' own inner `app.get(...)` guards are still scanned here.

const source = readFileSync(new URL("../src/server.ts", import.meta.url), "utf8");
const routeAuthSource = readFileSync(new URL("../src/routeAuth.ts", import.meta.url), "utf8");

/** Prefixes that must never be reachable without a valid session or API key. */
const PROTECTED_PREFIXES = ["/me/", "/v1/", "/api/", "/admin/", "/payments/"];
/** Protected-prefix routes that authenticate by another means (HMAC webhook). */
const PUBLIC_PROTECTED = new Set<string>([
  "POST /payments/chmaba/webhook",
  "POST /payments/chmabapay/webhook",
]);
const GUARDS = ["requireKey(", "requireAuth(", "requireAdmin("];

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
    while (i < source.length && depth > 0 && body.length < 8000) {
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

test("deny-by-default auth backstop is registered", () => {
  assert.match(source, /app\.addHook\(\s*"onRequest"/, "onRequest backstop hook is missing");
  assert.match(source, /from "\.\/routeAuth\.js"/, "server must use the shared route-auth policy");
  assert.match(routeAuthSource, /PROTECTED_PREFIXES/, "PROTECTED_PREFIXES list is missing");
  assert.match(
    routeAuthSource,
    /PUBLIC_PROTECTED_ROUTES[\s\S]{0,200}?\/payments\/chmaba\/webhook/,
    "the only public protected-prefix route (the webhook) must be declared",
  );
});

test("the router ignores a trailing slash so webhook variants resolve", () => {
  // The backstop normalizes `/webhook/` before allowing it, but the request
  // would still 404 unless the router treats `/a/b/` as `/a/b`. Both halves of
  // the fix must stay in place together.
  assert.match(
    source,
    /ignoreTrailingSlash:\s*true/,
    "Fastify must ignore trailing slashes for a slash-suffixed webhook delivery to reach its handler",
  );
  assert.match(
    routeAuthSource,
    /normalizeRoutePath/,
    "the public-route allowlist must normalize paths before matching",
  );
});

test("job ownership checks deny unowned jobs", () => {
  // Regression guard for P5: the permissive `job.userId && job.userId !== …`
  // form lets a job with no owner be read by any authenticated caller.
  assert.doesNotMatch(
    source,
    /job\.userId\s*&&\s*job\.userId\s*!==/,
    "permissive `job.userId && job.userId !== …` ownership check is present",
  );
  assert.match(
    source,
    /!job\.userId\s*\|\|\s*job\.userId\s*!==/,
    "expected the deny-unowned ownership form",
  );
});

test("upload-status routes enforce asset ownership", () => {
  // Regression guard for P6: every upload-status proxy must check the caller
  // owns the id before forwarding it upstream.
  const statusRoutes = routeRegistrations().filter((r) =>
    r.path.endsWith("/upload/status/:id"),
  );
  assert.ok(statusRoutes.length >= 3, `expected the 3 upload-status routes, found ${statusRoutes.length}`);
  for (const r of statusRoutes) {
    assert.match(
      r.body,
      /enforceFlow\(|requireOwnedAsset\(|assetOwnedByOtherUser\(/,
      `${r.method} ${r.path} does not enforce asset ownership`,
    );
  }
});

test("finished jobs record owned assets", () => {
  assert.match(
    source,
    /await recordOwnedAssets\(job\)/,
    "finalizeJob must record asset ownership for the caller's clips/uploads",
  );
});

test("every direct protected-prefix route carries an auth guard", () => {
  const offenders = routeRegistrations()
    .filter((r) => {
      if (!PROTECTED_PREFIXES.some((p) => r.path.startsWith(p))) return false;
      if (PUBLIC_PROTECTED.has(`${r.method} ${r.path}`)) return false;
      return !GUARDS.some((g) => r.body.includes(g));
    })
    .map((r) => `${r.method} ${r.path}`);

  assert.deepEqual(
    offenders,
    [],
    `protected routes registered without an auth guard: ${offenders.join(", ")}`,
  );
});

test("protected prefixes cover every route family the API exposes", () => {
  // Sanity: the scan actually found routes, so a parse failure cannot make the
  // guard test above vacuously pass.
  const routes = routeRegistrations();
  assert.ok(routes.length > 50, `expected many routes, parsed ${routes.length}`);
  assert.ok(
    routes.some((r) => r.path.startsWith("/me/")),
    "expected to parse /me/* routes",
  );
  assert.ok(
    routes.some((r) => r.path.startsWith("/admin/")),
    "expected to parse /admin/* routes",
  );
});
