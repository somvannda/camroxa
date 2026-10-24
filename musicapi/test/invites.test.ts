import { test } from "node:test";
import assert from "node:assert/strict";
import {
  coerceInvites,
  generateInviteCode,
  inviteRewardCredits,
  maskEmail,
  mergeInvites,
  normalizeInviteCode,
} from "../src/invites.js";

test("invite codes normalize case, spaces and punctuation", () => {
  assert.equal(normalizeInviteCode(" abcd-2345 "), "ABCD2345");
  assert.equal(normalizeInviteCode("a"), null);
  assert.equal(normalizeInviteCode(1234), null);
});

test("generated invite codes avoid ambiguous characters", () => {
  for (let i = 0; i < 50; i++) {
    const code = generateInviteCode();
    assert.equal(code.length, 8);
    assert.match(code, /^[A-HJ-NP-Z2-9]{8}$/);
  }
});

test("percent rewards round down but never pay zero on a real purchase", () => {
  assert.equal(inviteRewardCredits({ mode: "percent", value: 15 }, 1000), 150);
  assert.equal(inviteRewardCredits({ mode: "percent", value: 15 }, 50), 7);
  assert.equal(inviteRewardCredits({ mode: "percent", value: 15 }, 1), 1);
  assert.equal(inviteRewardCredits({ mode: "percent", value: 0 }, 100), 0);
  assert.equal(inviteRewardCredits({ mode: "percent", value: 15 }, 0), 0);
});

test("fixed rewards pay a flat amount independent of purchase size", () => {
  assert.equal(inviteRewardCredits({ mode: "fixed", value: 75 }, 5), 75);
  assert.equal(inviteRewardCredits({ mode: "fixed", value: 75 }, 10_000), 75);
  assert.equal(inviteRewardCredits({ mode: "fixed", value: 0 }, 500), 0);
});

test("stored settings are coerced back to safe defaults", () => {
  const defaults = coerceInvites(null);
  assert.equal(defaults.enabled, true);
  assert.deepEqual(defaults.inviter, { mode: "percent", value: 15 });
  assert.deepEqual(defaults.invitee, { mode: "percent", value: 15 });

  const clamped = coerceInvites({
    enabled: false,
    inviter: { mode: "percent", value: 250 },
    invitee: { mode: "fixed", value: 40 },
  });
  assert.equal(clamped.enabled, false);
  assert.equal(clamped.inviter.value, 100);
  assert.deepEqual(clamped.invitee, { mode: "fixed", value: 40 });
});

test("admin patches validate mode and amount bounds", () => {
  const current = coerceInvites(null);

  const valid = mergeInvites(current, {
    inviter: { mode: "fixed", value: 100 },
    invitee: { mode: "percent", value: 20 },
  });
  assert.equal(valid.ok, true);
  if (valid.ok) {
    assert.deepEqual(valid.value.inviter, { mode: "fixed", value: 100 });
    assert.deepEqual(valid.value.invitee, { mode: "percent", value: 20 });
  }

  assert.equal(mergeInvites(current, { inviter: { mode: "bogus" } }).ok, false);
  assert.equal(mergeInvites(current, { inviter: { value: -1 } }).ok, false);
  assert.equal(mergeInvites(current, { inviter: { mode: "percent", value: 101 } }).ok, false);
  assert.equal(mergeInvites(current, { enabled: "yes" }).ok, false);
});

test("email masking keeps only the first local-part character", () => {
  assert.equal(maskEmail("jane@example.com"), "j***@example.com");
  assert.equal(maskEmail("a@example.com"), "a*@example.com");
  assert.equal(maskEmail("not-an-email"), "***");
});
