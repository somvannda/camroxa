import { test } from "node:test";
import assert from "node:assert/strict";

import { ConcurrencyGate, QueueFullError } from "../src/concurrency.js";

const tick = () => new Promise((resolve) => setTimeout(resolve, 5));

test("gate enforces the global ceiling", async () => {
  const gate = new ConcurrencyGate(() => 1);
  const release1 = await gate.acquire("u", 5);

  let admitted = false;
  const pending = gate.acquire("u", 5).then((release) => {
    admitted = true;
    return release;
  });
  await tick();
  assert.equal(admitted, false);

  release1();
  const release2 = await pending;
  assert.equal(admitted, true);
  assert.equal(gate.stats().active, 1);
  release2();
  assert.equal(gate.stats().active, 0);
});

test("gate enforces the per-owner ceiling", async () => {
  const gate = new ConcurrencyGate(() => 10);
  const releaseA = await gate.acquire("alice", 1);

  let admitted = false;
  const pending = gate.acquire("bob", 1).then((release) => {
    admitted = true;
    return release;
  });
  await tick();
  // A different owner still has capacity.
  assert.equal(admitted, true);

  releaseA();
  (await pending)();
  assert.equal(gate.stats().active, 0);
});

test("bounded queue rejects with QueueFullError once at capacity", async () => {
  const gate = new ConcurrencyGate(() => 1, 1);
  const release1 = await gate.acquire("u", 5);
  void gate.acquire("u", 5); // occupies the single waiting slot
  await assert.rejects(gate.acquire("u", 5), QueueFullError);
  assert.equal(gate.stats().waiting, 1);
  release1();
});
