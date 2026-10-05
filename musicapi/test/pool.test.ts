import { test } from "node:test";
import assert from "node:assert/strict";

// `pool.ts` transitively imports `config.ts`, which fails fast without a strong
// JWT secret + cookie key. Set throwaway values before importing it.
process.env.JWT_SECRET ??= "unit-test-jwt-secret-0123456789abcdef0123456789";
process.env.COOKIE_ENCRYPTION_KEY ??=
  "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

const { orderByLoad } = await import("../src/pool.js");

type Client = { account: { id: string; type?: string } };

const clients: Client[] = [
  { account: { id: "a", type: "paid" } },
  { account: { id: "b", type: "free" } },
  { account: { id: "c", type: "free" } },
];

test("orderByLoad puts free accounts first when preferFree", () => {
  const ordered = orderByLoad(clients, () => 0, { preferFree: true });
  assert.equal(ordered[0]?.account.id, "b");
  assert.equal(ordered[ordered.length - 1]?.account.id, "a");
});

test("orderByLoad is least-loaded first by default", () => {
  const loads: Record<string, number> = { a: 2, b: 0, c: 1 };
  const ordered = orderByLoad(clients, (id) => loads[id] ?? 0);
  assert.deepEqual(
    ordered.map((c) => c.account.id),
    ["b", "c", "a"],
  );
});

test("orderByLoad sorts accounts already at maxPerAccount last", () => {
  const loads: Record<string, number> = { a: 0, b: 0, c: 4 };
  const ordered = orderByLoad(clients, (id) => loads[id] ?? 0, { maxPerAccount: 4 });
  assert.equal(ordered[ordered.length - 1]?.account.id, "c");
});
