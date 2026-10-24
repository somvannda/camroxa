import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { test } from "node:test";
import {
  mapResendEvent,
  suppressionReasonFor,
  verifyResendSignature,
} from "../src/resendWebhook.js";

const KEY = Buffer.from("test-webhook-key");
const SECRET = `whsec_${KEY.toString("base64")}`;
const NOW = 1_760_000_000;

function sign(id: string, timestamp: string, body: string, key = KEY): string {
  return createHmac("sha256", key).update(`${id}.${timestamp}.${body}`, "utf8").digest("base64");
}

const BODY = JSON.stringify({
  type: "email.delivered",
  data: { email_id: "abc-123", to: ["user@example.com"], subject: "Hi" },
});

test("a correctly signed delivery is accepted", () => {
  const id = "msg_1";
  const ts = String(NOW);
  const signature = `v1,${sign(id, ts, BODY)}`;
  assert.equal(
    verifyResendSignature(BODY, { id, timestamp: ts, signature }, SECRET, NOW),
    true,
  );
});

test("multiple v1 signatures are tolerated (key rotation)", () => {
  const id = "msg_2";
  const ts = String(NOW);
  const good = `v1,${sign(id, ts, BODY)}`;
  const signature = `v1,${createHmac("sha256", Buffer.from("old")).update("x").digest("base64")} ${good}`;
  assert.equal(
    verifyResendSignature(BODY, { id, timestamp: ts, signature }, SECRET, NOW),
    true,
  );
});

test("a wrong secret is rejected", () => {
  const id = "msg_3";
  const ts = String(NOW);
  const signature = `v1,${sign(id, ts, BODY, Buffer.from("wrong"))}`;
  assert.equal(
    verifyResendSignature(BODY, { id, timestamp: ts, signature }, SECRET, NOW),
    false,
  );
});

test("a body modified after signing is rejected", () => {
  const id = "msg_4";
  const ts = String(NOW);
  const signature = `v1,${sign(id, ts, BODY)}`;
  assert.equal(
    verifyResendSignature(`${BODY} `, { id, timestamp: ts, signature }, SECRET, NOW),
    false,
  );
});

test("a replayed delivery outside the tolerance window is rejected", () => {
  const id = "msg_5";
  const ts = String(NOW);
  const signature = `v1,${sign(id, ts, BODY)}`;
  // Same signature, ten minutes later.
  assert.equal(
    verifyResendSignature(BODY, { id, timestamp: ts, signature }, SECRET, NOW + 600),
    false,
  );
});

test("missing headers or secret fail closed", () => {
  assert.equal(
    verifyResendSignature(BODY, { id: undefined, timestamp: undefined, signature: undefined }, SECRET, NOW),
    false,
  );
  assert.equal(
    verifyResendSignature(BODY, { id: "m", timestamp: String(NOW), signature: "v1,x" }, "", NOW),
    false,
  );
});

test("delivery-state events map to our vocabulary", () => {
  const delivered = mapResendEvent({
    type: "email.delivered",
    data: { email_id: "e1", to: ["User@Example.com"], subject: "S" },
  });
  assert.deepEqual(delivered, {
    type: "delivered",
    emailId: "e1",
    recipient: "user@example.com",
    subject: "S",
    url: null,
  });

  for (const [event, expected] of [
    ["email.bounced", "bounced"],
    ["email.complained", "complained"],
    ["email.failed", "failed"],
  ] as const) {
    const mapped = mapResendEvent({ type: event, data: { email_id: "e2", to: ["a@b.c"] } });
    assert.equal(mapped?.type, expected);
  }
});

test("opens and clicks are not consumed from webhooks", () => {
  // They are recorded by our own pixel/redirect; consuming them here would
  // double-count every engagement.
  assert.equal(mapResendEvent({ type: "email.opened", data: { email_id: "e3" } }), null);
  assert.equal(
    mapResendEvent({ type: "email.clicked", data: { email_id: "e3", click: { link: "https://x" } } }),
    null,
  );
  assert.equal(mapResendEvent({ type: "email.sent", data: { email_id: "e3" } }), null);
});

test("malformed payloads are ignored rather than throwing", () => {
  assert.equal(mapResendEvent(null), null);
  assert.equal(mapResendEvent("nope"), null);
  assert.equal(mapResendEvent({ type: "email.delivered" }), null);
  assert.equal(mapResendEvent({ type: "email.delivered", data: {} }), null);
});

test("bounces and complaints suppress the address", () => {
  assert.equal(suppressionReasonFor("bounced"), "bounce");
  assert.equal(suppressionReasonFor("complained"), "complaint");
  assert.equal(suppressionReasonFor("delivered"), null);
  assert.equal(suppressionReasonFor("failed"), null);
});
