import { test } from "node:test";
import assert from "node:assert/strict";
import { compact, num, percent, usd } from "../lib/format.ts";

test("usd formats two decimals", () => {
  assert.equal(usd(1.5), "$1.50");
  assert.equal(usd(0), "$0.00");
  assert.equal(usd(1234.567), "$1234.57");
});

test("num renders an em dash for empty and formats numbers", () => {
  assert.equal(num(null), "—");
  assert.equal(num(undefined), "—");
  assert.equal(num(""), "—");
  assert.equal(num(1200), "1,200");
  assert.equal(num("250"), "250");
});

test("percent handles a zero denominator", () => {
  assert.equal(percent(0, 0), "—");
  assert.equal(percent(1, 2), "50.0%");
  assert.equal(percent(3, 3), "100.0%");
});

test("compact abbreviates large numbers", () => {
  assert.equal(compact(1500), "1.5K");
  assert.equal(compact(0), "0");
});
