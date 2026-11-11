import { test } from "node:test";
import assert from "node:assert/strict";

// config.ts refuses to load without these; other suites set them too, but a
// standalone run of this file must not depend on import order.
process.env.JWT_SECRET ??= "unit-test-jwt-secret-0123456789abcdef0123456789";
process.env.COOKIE_ENCRYPTION_KEY ??= "0123456789abcdef".repeat(4);
process.env.TWOCAPTCHA_MAX_CONCURRENT ??= "2";
process.env.TWOCAPTCHA_NOSLOT_RETRY_DELAY_MS ??= "0";

const {
  CaptchaUnavailableError,
  SolveSemaphore,
  isCaptchaUnavailableError,
  isNoSlotAvailableError,
  solveCaptchaForAccount,
} = await import("../src/captcha.js");

const noSlot = (message = "Captcha Queue exceeded maximum capacity") =>
  Object.assign(new Error(message), { err: "ERROR_NO_SLOT_AVAILABLE" });

test("no-slot detection reads the raw 2Captcha code, numeric code, or message", () => {
  assert.equal(isNoSlotAvailableError(noSlot()), true);
  assert.equal(isNoSlotAvailableError({ code: 11 }), true);
  assert.equal(
    isNoSlotAvailableError(
      new Error("Captcha Queue exceeded maximum capacity. Please wait a few moments..."),
    ),
    true,
  );
  assert.equal(isNoSlotAvailableError(Object.assign(new Error("x"), { err: "ERROR_ZERO_BALANCE" })), false);
  assert.equal(isNoSlotAvailableError(new Error("invalid model name")), false);
});

test("solve gate never runs more solves than its ceiling", async () => {
  const gate = new SolveSemaphore(2);
  let active = 0;
  let peak = 0;

  const task = () =>
    gate.run(async () => {
      active += 1;
      peak = Math.max(peak, active);
      await new Promise((resolve) => setTimeout(resolve, 10));
      active -= 1;
    });

  await Promise.all(Array.from({ length: 6 }, task));

  assert.equal(peak, 2);
  assert.deepEqual(gate.stats, { active: 0, waiting: 0, max: 2 });
});

test("the production solve path holds at most TWOCAPTCHA_MAX_CONCURRENT solves", async () => {
  let active = 0;
  let peak = 0;
  const solver = {
    async cloudflareTurnstile() {
      active += 1;
      peak = Math.max(peak, active);
      await new Promise((resolve) => setTimeout(resolve, 15));
      active -= 1;
      return { data: "token" };
    },
  };

  const run = () => solveCaptchaForAccount({ twoCaptchaKey: "test-key" }, { solver });
  const tokens = await Promise.all(Array.from({ length: 5 }, run));

  assert.deepEqual(tokens, Array(5).fill("token"));
  assert.ok(peak <= 2, `peak concurrency ${peak} exceeded the cap`);
});

test("a single no-slot rejection is retried after the configured pause", async () => {
  let calls = 0;
  const sleeps: number[] = [];
  const solver = {
    async cloudflareTurnstile() {
      calls += 1;
      if (calls === 1) throw noSlot();
      return { data: "solved-token" };
    },
  };

  const token = await solveCaptchaForAccount(
    { twoCaptchaKey: "test-key" },
    {
      solver,
      sleep: async (ms) => {
        sleeps.push(ms);
      },
      noSlotRetryDelayMs: 1234,
    },
  );

  assert.equal(token, "solved-token");
  assert.equal(calls, 2);
  assert.deepEqual(sleeps, [1234]);
});

test("a persistent no-slot rejection surfaces as CaptchaUnavailableError", async () => {
  const solver = {
    async cloudflareTurnstile() {
      throw noSlot();
    },
  };

  await assert.rejects(
    () =>
      solveCaptchaForAccount(
        { twoCaptchaKey: "test-key" },
        { solver, sleep: async () => {}, noSlotRetryDelayMs: 1 },
      ),
    (err: unknown) =>
      isCaptchaUnavailableError(err) &&
      err instanceof CaptchaUnavailableError &&
      /queue is full/i.test(err.message),
  );
});

test("a non-capacity 2Captcha error is not retried", async () => {
  let calls = 0;
  const solver = {
    async cloudflareTurnstile() {
      calls += 1;
      throw Object.assign(new Error("There aren't enough funds"), { err: "ERROR_ZERO_BALANCE" });
    },
  };

  await assert.rejects(
    () =>
      solveCaptchaForAccount(
        { twoCaptchaKey: "test-key" },
        { solver, sleep: async () => {}, noSlotRetryDelayMs: 1 },
      ),
    /enough funds/,
  );
  assert.equal(calls, 1);
});

test("a solve that returns no token is rejected", async () => {
  const solver = { async cloudflareTurnstile() { return {}; } };

  await assert.rejects(
    () => solveCaptchaForAccount({ twoCaptchaKey: "test-key" }, { solver }),
    /returned no token/,
  );
});

test("a missing API key fails before any solve", async () => {
  await assert.rejects(
    () => solveCaptchaForAccount({ twoCaptchaKey: "" }, { solver: { async cloudflareTurnstile() { return { data: "x" }; } } }),
    /TWOCAPTCHA_KEY is required/,
  );
});
