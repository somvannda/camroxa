/**
 * smoke-test-reachability — verifies the *whole* registered route surface.
 *
 * Why this exists: grepping `app.get/post(...)` in src/server.ts undercounts badly (142 literal
 * matches vs. 205 real routes) because routes are also registered through helpers (`clipRoute`,
 * `detailRoute`, `meDetailRoute`) and through loops. Fastify's own `printRoutes()` is the only
 * ground truth, so this script boots the server in-process, reads that tree, then hits every route.
 *
 * It probes two tiers and never spends credits:
 *   T1 — no credentials at all. Auth-gated routes must answer 401.
 *   T2 — valid API key + empty body, only for POST on the public surfaces (`/v1/*`, `/api/v1/*`).
 *        Input validation must answer 400 (not 500, not 401, not a silent success).
 *
 * A live success path (T3: real generation) is deliberately NOT included — that spends real Suno
 * quota. See ENDPOINT_STATUS.md §Next Priorities.
 *
 * Usage:
 *   npm run serve                  # in another terminal
 *   npx tsx scripts/smoke-test-reachability.ts
 *
 * Env: BASE (default http://localhost:4003), TEST_KEY (default sk-test-123).
 */

import "dotenv/config";
import { AccountPool } from "../src/pool.js";
import { buildServer } from "../src/server.js";

const BASE = process.env.BASE || "http://localhost:4003";
const KEY = process.env.TEST_KEY || "sk-test-123";
const PLACEHOLDER = "00000000-0000-0000-0000-000000000000";

const pool = await AccountPool.fromDb();
const app = await buildServer({ pool });
const tree = app.printRoutes({ commonPrefix: false });
await app.close();

interface R { method: string; path: string; }
const routes: R[] = [];
const stack: string[] = [];
for (const line of tree.split("\n")) {
  const m = line.match(/^([\u2502 ]*)[\u251c\u2514]\u2500\u2500 (.*)$/);
  if (!m) continue;
  const depth = m[1].length / 4;
  const rest = m[2];
  const mm = rest.match(/^(.*?)\s\(([A-Z, ]+)\)$/);
  let name = rest;
  let methods: string[] = [];
  if (mm) { name = mm[1]; methods = mm[2].split(",").map((s) => s.trim()); }
  stack[depth] = name;
  stack.length = depth + 1;
  if (methods.length) {
    const full = stack.join("");
    for (const method of methods) {
      if (method === "HEAD" || method === "OPTIONS") continue;
      routes.push({ method, path: full });
    }
  }
}

function materialize(p: string): string {
  return p.replace(/:[^/]+/g, PLACEHOLDER);
}

async function hit(method: string, path: string, headers: Record<string, string>, body?: string) {
  try {
    const res = await fetch(BASE + materialize(path), {
      method,
      headers: { "content-type": "application/json", ...headers },
      body,
    });
    const text = await res.text();
    return { status: res.status, body: text.slice(0, 140) };
  } catch (e) {
    return { status: 0, body: String(e).slice(0, 140) };
  }
}

const rows: Array<{ method: string; path: string; t1: number; t2?: number; note: string }> = [];
const notFound: string[] = [];
const t2Mismatch: string[] = [];

for (const r of routes) {
  const t1 = await hit(r.method, r.path, {}, r.method === "GET" ? undefined : "{}");
  const isApiKeySurface = r.path.startsWith("/v1/") || r.path.startsWith("/api/v1/");
  let t2: number | undefined;
  if (r.method === "POST" && isApiKeySurface) {
    const res = await hit(r.method, r.path, { authorization: `Bearer ${KEY}` }, "{}");
    t2 = res.status;
  }
  let note = "";
  if (t1.status === 404) { note = "NOT-ROUTED"; notFound.push(`${r.method} ${r.path}`); }
  if (t2 !== undefined && t2 !== 400) {
    note += (note ? " " : "") + "T2!=" + t2;
    t2Mismatch.push(`${r.method} ${r.path} -> ${t2}`);
  }
  rows.push({ method: r.method, path: r.path, t1: t1.status, t2, note });
}

console.log(`ROUTES=${rows.length}`);
console.log("");
for (const row of rows) {
  const t2s = row.t2 === undefined ? "" : `  T2=${row.t2}`;
  const status = String(row.t1).padEnd(3);
  console.log(`${row.method.padEnd(6)} ${materialize(row.path).padEnd(52)} T1=${status}${t2s}${row.note ? "   << " + row.note : ""}`);
}

console.log("");
console.log(`NOT-ROUTED (T1 404): ${notFound.length}`);
for (const n of notFound) console.log("  " + n);
console.log(`T2 (valid key + {}) != 400: ${t2Mismatch.length}`);
for (const n of t2Mismatch) console.log("  " + n);

const statusCounts: Record<string, number> = {};
for (const row of rows) statusCounts[String(row.t1)] = (statusCounts[String(row.t1)] || 0) + 1;
console.log("");
console.log("T1 status histogram:", JSON.stringify(statusCounts));

// A T1 of 0 means the base URL was unreachable — fail loudly rather than reporting all-green.
const unreachable = rows.filter((r) => r.t1 === 0).length;
if (unreachable > 0) {
  console.error(`\nFAIL: ${unreachable} routes were unreachable — is the core API running at ${BASE}?`);
  process.exit(1);
}
process.exit(0);
