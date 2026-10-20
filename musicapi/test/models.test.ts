import { test } from "node:test";
import assert from "node:assert/strict";

import {
  canSpendAllowance,
  defaultRoutingPolicy,
  freeModelRoutingPolicy,
  isAllowanceModel,
  modelLabel,
  normalizeModel,
} from "../src/models.js";

test("normalizeModel maps retired keys onto current Suno models", () => {
  assert.equal(normalizeModel("V6"), "chirp-hawk");
  assert.equal(normalizeModel("v6-wild"), "chirp-hawk-wild");
  assert.equal(normalizeModel("v6_mini"), "chirp-goose");
  assert.equal(normalizeModel("chirp-v5-5"), "chirp-hawk");
  assert.equal(normalizeModel("chirp-v3-5-b"), "chirp-goose");
});

test("normalizeModel passes current/unknown keys through and blanks empties", () => {
  assert.equal(normalizeModel("chirp-hawk"), "chirp-hawk");
  assert.equal(normalizeModel("some-future-model"), "some-future-model");
  assert.equal(normalizeModel(""), undefined);
  assert.equal(normalizeModel("   "), undefined);
  assert.equal(normalizeModel(undefined), undefined);
  assert.equal(normalizeModel(null), undefined);
});

test("defaultRoutingPolicy prefers free only for the free-tier model", () => {
  assert.equal(defaultRoutingPolicy("chirp-goose"), "prefer_free");
  assert.equal(defaultRoutingPolicy("v6-mini"), "prefer_free");
  assert.equal(defaultRoutingPolicy("chirp-hawk"), "paid_only");
  assert.equal(defaultRoutingPolicy(undefined), "paid_only");
});

test("isAllowanceModel matches the configured free model across aliases", () => {
  const tier = { enabled: true, model: "chirp-goose" };
  assert.equal(isAllowanceModel("chirp-goose", tier), true);
  assert.equal(isAllowanceModel("v6-mini", tier), true);
  assert.equal(isAllowanceModel("V6_MINI", tier), true);
  assert.equal(isAllowanceModel("chirp-v6-mini", tier), true);
  assert.equal(isAllowanceModel("chirp-hawk", tier), false);
  assert.equal(isAllowanceModel("v6-wild", tier), false);
  // An omitted model must never spend the allowance: Suno's default is premium.
  assert.equal(isAllowanceModel(undefined, tier), false);
  assert.equal(isAllowanceModel("", tier), false);
  // Disabled allowance falls back to purchased credits for every model.
  assert.equal(isAllowanceModel("chirp-goose", { ...tier, enabled: false }), false);
});

test("modelLabel renders the customer-facing version name", () => {
  assert.equal(modelLabel("chirp-hawk"), "V6");
  assert.equal(modelLabel("v6-wild"), "V6-WILD");
  assert.equal(modelLabel("v6-mini"), "V6-Mini");
  assert.equal(modelLabel("some-future-model"), "some-future-model");
  assert.equal(modelLabel(undefined), null);
});

test("freeModelRoutingPolicy keeps V6-Mini on free accounts unless fallback is on", () => {
  assert.equal(freeModelRoutingPolicy(false), "free_only");
  assert.equal(freeModelRoutingPolicy(true), "prefer_free");
});

test("canSpendAllowance unlocks premium models only after a purchase", () => {
  const tier = { enabled: true, model: "chirp-goose" };
  // Default: only the free model may spend the allowance.
  assert.equal(canSpendAllowance("v6-mini", tier, false), true);
  assert.equal(canSpendAllowance("chirp-hawk", tier, false), false);
  assert.equal(canSpendAllowance("v6-wild", tier, false), false);
  // A credit-pack purchase makes the remaining allowance universal.
  assert.equal(canSpendAllowance("chirp-hawk", tier, true), true);
  assert.equal(canSpendAllowance("v6-wild", tier, true), true);
  // Unknown/omitted models never spend it.
  assert.equal(canSpendAllowance(undefined, tier, true), false);
  assert.equal(canSpendAllowance("", tier, true), false);
  // Disabled allowance wins over the universal flag.
  assert.equal(canSpendAllowance("chirp-hawk", { ...tier, enabled: false }, true), false);
});
