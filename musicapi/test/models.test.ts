import { test } from "node:test";
import assert from "node:assert/strict";

import { defaultRoutingPolicy, normalizeModel } from "../src/models.js";

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
