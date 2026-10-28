import { test } from "node:test";
import assert from "node:assert/strict";

const { SunoHttpError, isCapacityExhaustionError, isRetryableSunoError } = await import("../src/sunoError.js");

test("402/429/5xx SunoHttpError are retryable", () => {
  assert.equal(isRetryableSunoError(new SunoHttpError("x", 402)), true);
  assert.equal(isRetryableSunoError(new SunoHttpError("x", 429)), true);
  assert.equal(isRetryableSunoError(new SunoHttpError("x", 500)), true);
  assert.equal(isRetryableSunoError(new SunoHttpError("x", 503)), true);
});

test("rate_limited error_type is retryable regardless of status", () => {
  assert.equal(isRetryableSunoError(new SunoHttpError("x", 400, "rate_limited")), true);
});

test("400/422 SunoHttpError stay terminal", () => {
  assert.equal(
    isRetryableSunoError(new SunoHttpError("generate/v2 failed (400): bad model", 400)),
    false,
  );
  assert.equal(
    isRetryableSunoError(new SunoHttpError("generate/v2 failed (422): bad prompt", 422)),
    false,
  );
});

test("plain Error falls back to the message regex", () => {
  assert.equal(isRetryableSunoError(new Error("generate/v2 failed (429): Too many requests.")), true);
  assert.equal(isRetryableSunoError(new Error("captcha required")), true);
  assert.equal(isRetryableSunoError(new Error("generate/v2 failed (402): not enough credits")), true);
  assert.equal(isRetryableSunoError(new Error("invalid model name")), false);
});

test("non-Error values are handled", () => {
  assert.equal(isRetryableSunoError("timeout"), true);
  assert.equal(isRetryableSunoError("nope"), false);
});

test("capacity exhaustion covers pool selection and provider 402", () => {
  // Pool selection: every account was below the credit floor.
  assert.equal(
    isCapacityExhaustionError(new Error("No Suno account with available credits for this model.")),
    true,
  );
  // Pool selection with a paid-only policy.
  assert.equal(
    isCapacityExhaustionError(
      new Error("No paid Suno account is available for this model; premium models require a paid account."),
    ),
    true,
  );
  // An account probed as unreachable is not capacity, but a drained one is.
  assert.equal(
    isCapacityExhaustionError(new Error("No usable account available for this model.")),
    true,
  );
  assert.equal(isCapacityExhaustionError(new SunoHttpError("generate/v2 failed", 402)), true);
  assert.equal(
    isCapacityExhaustionError(new Error('generate/v2 failed (402): {"status_code": 402}')),
    true,
  );
});

test("content-policy and server errors are not capacity exhaustion", () => {
  assert.equal(
    isCapacityExhaustionError(
      new SunoHttpError("generate/v2 failed (400): SENSITIVE_WORD_ERROR", 400),
    ),
    false,
  );
  assert.equal(
    isCapacityExhaustionError(new SunoHttpError("generate/v2 failed", 500)),
    false,
  );
  assert.equal(isCapacityExhaustionError(new Error("invalid model name")), false);
});

