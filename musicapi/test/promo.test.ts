import assert from "node:assert/strict";
import { test } from "node:test";
import {
  coercePreset,
  computePromoQuote,
  generatePromoCode,
  type PromoCode,
} from "../src/promo.js";

function promo(overrides: Partial<PromoCode> = {}): PromoCode {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    code: "CAMX-ABC234",
    kind: "percent",
    value: 20,
    user_id: null,
    max_redemptions: 1,
    redeemed_count: 0,
    expires_at: null,
    is_active: true,
    ...overrides,
  };
}

test("a percent code discounts the pack price and keeps the credits", () => {
  const result = computePromoQuote(promo({ value: 20 }), 5, 1000);
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.quote.amount, 4);
  assert.equal(result.quote.discount, 1);
  assert.equal(result.quote.credits, 1000);
});

test("percent discount rounds to cents, not to whole units", () => {
  const result = computePromoQuote(promo({ value: 15 }), 20, 5500);
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.quote.amount, 17);
  assert.equal(result.quote.discount, 3);

  const awkward = computePromoQuote(promo({ value: 33 }), 5, 1000);
  assert.equal(awkward.ok, true);
  if (!awkward.ok) return;
  assert.equal(awkward.quote.discount, 1.65);
  assert.equal(awkward.quote.amount, 3.35);
});

test("a percent code can never reduce the charge to zero", () => {
  const result = computePromoQuote(promo({ value: 100 }), 5, 1000);
  assert.equal(result.ok, false);
  if (result.ok) return;
  assert.match(result.error, /full price/i);
});

test("99 percent still leaves a positive charge", () => {
  const result = computePromoQuote(promo({ value: 99 }), 5, 1000);
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.quote.amount, 0.05);
});

test("pg returns NUMERIC as a string; the quote must still be numeric", () => {
  const result = computePromoQuote(
    promo({ value: "20" as unknown as number }),
    5,
    1000,
  );
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.quote.amount, 4);
  assert.equal(result.quote.value, 20);
  assert.equal(typeof result.quote.amount, "number");
});

test("a bonus code adds credits and leaves the price alone", () => {
  const result = computePromoQuote(promo({ kind: "credit_bonus", value: 500 }), 5, 1000);
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.quote.amount, 5);
  assert.equal(result.quote.discount, 0);
  assert.equal(result.quote.credits, 1500);
});

test("a bonus code floors fractional credits", () => {
  const result = computePromoQuote(promo({ kind: "credit_bonus", value: 500.9 }), 5, 1000);
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.quote.credits, 1500);
});

test("generated codes avoid ambiguous characters", () => {
  for (let i = 0; i < 40; i += 1) {
    const code = generatePromoCode();
    assert.match(code, /^CAMX-[A-Z2-9]{6}$/);
    // O/0 and I/1 are excluded so a code read off a screen still works.
    assert.doesNotMatch(code.slice(5), /[OI01]/);
  }
});

test("coercePreset validates and clamps campaign recipes", () => {
  assert.deepEqual(coercePreset({ kind: "percent", value: 20, expiresDays: 7 }), {
    kind: "percent",
    value: 20,
    expiresDays: 7,
  });

  // 100% cannot be settled by a gateway, so it clamps to 99.
  assert.equal(coercePreset({ kind: "percent", value: 100 })?.value, 99);
  // Expiry is bounded so a typo cannot produce a 10-year code.
  assert.equal(coercePreset({ kind: "percent", value: 10, expiresDays: 3650 })?.expiresDays, 90);
  assert.equal(coercePreset({ kind: "percent", value: 10, expiresDays: 0 })?.expiresDays, 1);

  assert.equal(coercePreset({ kind: "nope", value: 10 }), null);
  assert.equal(coercePreset({ kind: "percent", value: 0 }), null);
  assert.equal(coercePreset({ kind: "percent", value: -5 }), null);
  assert.equal(coercePreset({ kind: "percent", value: "abc" }), null);
  assert.equal(coercePreset(null), null);
  assert.equal(coercePreset(undefined), null);
});
