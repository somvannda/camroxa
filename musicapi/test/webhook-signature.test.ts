import { test } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import {
  SIGNATURE_TOLERANCE_SECONDS,
  findReferenceId,
  verifyChmabaSignature,
} from "../src/webhookSignature.js";

const SECRET = "whsec_test_secret";
const T = 1_700_000_000;
const BODY = '{"event":"payment.completed","data":{"reference_id":"tx-1"}}';

function sign(body: string, t: number, secret = SECRET): string {
  const v1 = createHmac("sha256", secret).update(`${t}.${body}`, "utf8").digest("hex");
  return `t=${t},v1=${v1}`;
}

test("accepts a correctly signed payload within the replay window", () => {
  assert.equal(verifyChmabaSignature(BODY, sign(BODY, T), SECRET, T), true);
});

test("rejects a tampered body", () => {
  assert.equal(verifyChmabaSignature(BODY + " ", sign(BODY, T), SECRET, T), false);
});

test("rejects a signature from the wrong secret", () => {
  assert.equal(verifyChmabaSignature(BODY, sign(BODY, T, "other"), SECRET, T), false);
});

test("rejects a stale or future timestamp outside the tolerance", () => {
  const h = sign(BODY, T);
  assert.equal(verifyChmabaSignature(BODY, h, SECRET, T + SIGNATURE_TOLERANCE_SECONDS), true);
  assert.equal(verifyChmabaSignature(BODY, h, SECRET, T + SIGNATURE_TOLERANCE_SECONDS + 1), false);
  assert.equal(verifyChmabaSignature(BODY, h, SECRET, T - SIGNATURE_TOLERANCE_SECONDS - 1), false);
});

test("rejects missing or malformed headers and empty secrets", () => {
  assert.equal(verifyChmabaSignature(BODY, undefined, SECRET, T), false);
  assert.equal(verifyChmabaSignature(BODY, "", SECRET, T), false);
  assert.equal(verifyChmabaSignature(BODY, "v1=abc", SECRET, T), false);
  assert.equal(verifyChmabaSignature(BODY, "t=notanumber,v1=abc", SECRET, T), false);
  assert.equal(verifyChmabaSignature(BODY, sign(BODY, T), "", T), false);
});

test("findReferenceId locates a nested reference_id", () => {
  assert.equal(findReferenceId(JSON.parse(BODY)), "tx-1");
  assert.equal(findReferenceId({ a: [{ b: { reference_id: "  xyz  " } }] }), "xyz");
  assert.equal(findReferenceId({ a: 1 }), null);
  assert.equal(findReferenceId("nope"), null);
});
