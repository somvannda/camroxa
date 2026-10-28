import { test } from "node:test";
import assert from "node:assert/strict";

// `pool.ts` transitively imports `config.ts`, which fails fast without a strong
// JWT secret + cookie key. Set throwaway values before importing it.
process.env.JWT_SECRET ??= "unit-test-jwt-secret-0123456789abcdef0123456789";
process.env.COOKIE_ENCRYPTION_KEY ??=
  "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

const { orderByLoad, orderForDispatch, belowCreditFloor, lowCreditSummary, PoolCreditExhaustedError } =
  await import("../src/pool.js");

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

test("belowCreditFloor rejects accounts under the floor", () => {
  assert.equal(belowCreditFloor(2, 10), true);
  assert.equal(belowCreditFloor(9, 10), true);
  assert.equal(belowCreditFloor(10, 10), false);
  assert.equal(belowCreditFloor(50, 10), false);
});

test("belowCreditFloor never treats an empty account as usable", () => {
  // A floor of 0 (legacy setting) must still exclude exactly-empty accounts.
  assert.equal(belowCreditFloor(0, 0), true);
  assert.equal(belowCreditFloor(1, 0), false);
});

test("lowCreditSummary names every drained account and the floor", () => {
  assert.equal(
    lowCreditSummary(
      [
        { id: "acct-1", credits: 3 },
        { id: "acct-2", credits: 0 },
      ],
      10,
    ),
    "acct-1 (3), acct-2 (0) — floor 10 credits",
  );
});

test("PoolCreditExhaustedError keeps account labels out of the user-facing text", () => {
  const err = new PoolCreditExhaustedError(
    "Music generation is temporarily unavailable.",
    lowCreditSummary([{ id: "ops@example.com", credits: 2 }], 10),
  );
  assert.equal(err.name, "PoolCreditExhaustedError");
  assert.ok(err instanceof Error);
  assert.equal(err.message, "Music generation is temporarily unavailable.");
  assert.doesNotMatch(err.message, /ops@example\.com/);
  assert.match(err.detail, /ops@example\.com \(2\)/);
});

const ids = (ordered: Client[]): string[] => ordered.map((c) => c.account.id);

test("orderForDispatch with strategy off matches the legacy load ordering", () => {
  const loads: Record<string, number> = { a: 2, b: 0, c: 1 };
  const load = (id: string): number => loads[id] ?? 0;
  const credits: Record<string, number> = { a: 10, b: 500, c: 100 };
  assert.deepEqual(
    ids(orderForDispatch(clients, { load, credits: (id) => credits[id] ?? 0, strategy: "off" })),
    ids(orderByLoad(clients, load)),
  );
});

test("orderForDispatch ignores credits when strategy is off", () => {
  // b has the most credits but the highest load; off must not reorder on credits.
  const loads: Record<string, number> = { a: 0, b: 3, c: 1 };
  const credits: Record<string, number> = { a: 10, b: 500, c: 100 };
  const ordered = orderForDispatch(clients, {
    load: (id) => loads[id] ?? 0,
    credits: (id) => credits[id] ?? 0,
    strategy: "off",
  });
  assert.deepEqual(ids(ordered), ["a", "c", "b"]);
});

test("credit-aware ordering puts the highest balance first", () => {
  const credits: Record<string, number> = { a: 10, b: 500, c: 100 };
  const ordered = orderForDispatch(clients, {
    credits: (id) => credits[id] ?? 0,
    strategy: "balanced",
  });
  assert.deepEqual(ids(ordered), ["b", "c", "a"]);
});

test("credit-aware ordering still prefers free accounts when preferFree", () => {
  // a is paid with the most credits; prefer_free must keep free accounts ahead.
  const credits: Record<string, number> = { a: 1000, b: 10, c: 10 };
  const ordered = orderForDispatch(clients, {
    credits: (id) => credits[id] ?? 0,
    preferFree: true,
    strategy: "balanced",
  });
  assert.equal(ordered[0]?.account.id, "b");
  assert.equal(ordered[ordered.length - 1]?.account.id, "a");
});

test("credit-aware ordering keeps an over-cap account last despite credits", () => {
  const loads: Record<string, number> = { a: 0, b: 4, c: 0 };
  const credits: Record<string, number> = { a: 10, b: 100_000, c: 10 };
  const ordered = orderForDispatch(clients, {
    load: (id) => loads[id] ?? 0,
    credits: (id) => credits[id] ?? 0,
    maxPerAccount: 4,
    strategy: "balanced",
  });
  assert.equal(ordered[ordered.length - 1]?.account.id, "b");
});

test("credit-aware ordering falls back to least-loaded on equal balances", () => {
  const loads: Record<string, number> = { a: 3, b: 0, c: 1 };
  const credits: Record<string, number> = { a: 100, b: 100, c: 100 };
  const ordered = orderForDispatch(clients, {
    load: (id) => loads[id] ?? 0,
    credits: (id) => credits[id] ?? 0,
    strategy: "balanced",
  });
  assert.deepEqual(ids(ordered), ["b", "c", "a"]);
});
