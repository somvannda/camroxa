import { test } from "node:test";
import assert from "node:assert/strict";
import {
  base32Decode,
  base32Encode,
  generateTotpSecret,
  hotp,
  otpauthUrl,
  verifyTotp,
} from "../src/totp.js";

// RFC 6238 Appendix B test vectors (SHA-1). The shared secret is the ASCII
// string "12345678901234567890".
const SECRET_B32 = base32Encode(Buffer.from("12345678901234567890", "ascii"));

test("base32 round-trips", () => {
  const buf = Buffer.from([0xde, 0xad, 0xbe, 0xef, 0x00, 0x42]);
  assert.deepEqual(base32Decode(base32Encode(buf)), buf);
  assert.equal(base32Decode(base32Encode(Buffer.from("12345678901234567890", "ascii"))).toString(), "12345678901234567890");
});

test("generateTotpSecret yields a decodable 20-byte secret", () => {
  const s = generateTotpSecret();
  assert.match(s, /^[A-Z2-7]+$/);
  assert.equal(base32Decode(s).length, 20);
});

test("hotp matches RFC 6238 vectors (8 digits)", () => {
  const key = base32Decode(SECRET_B32);
  const vectors: Array<[number, string]> = [
    [59, "94287082"],
    [1111111109, "07081804"],
    [1111111111, "14050471"],
    [1234567890, "89005924"],
    [2000000000, "69279037"],
    [20000000000, "65353130"],
  ];
  for (const [t, expected] of vectors) {
    assert.equal(hotp(key, Math.floor(t / 30), 8), expected, `t=${t}`);
  }
});

test("verifyTotp accepts the current 6-digit code and rejects wrong input", () => {
  const code = hotp(base32Decode(SECRET_B32), Math.floor(59 / 30), 6);
  assert.equal(verifyTotp(SECRET_B32, code, { now: 59_000 }), true);
  assert.equal(verifyTotp(SECRET_B32, "000000", { now: 59_000 }), false);
  assert.equal(verifyTotp(SECRET_B32, "abc123", { now: 59_000 }), false);
  assert.equal(verifyTotp("not-base32!!", code, { now: 59_000 }), false);
});

test("verifyTotp allows one step of clock skew", () => {
  const prev = hotp(base32Decode(SECRET_B32), Math.floor(59 / 30) - 1, 6);
  assert.equal(verifyTotp(SECRET_B32, prev, { now: 59_000, window: 1 }), true);
  assert.equal(verifyTotp(SECRET_B32, prev, { now: 59_000, window: 0 }), false);
});

test("otpauthUrl carries the secret and label", () => {
  const url = otpauthUrl({ secret: SECRET_B32, label: "admin@example.com" });
  assert.match(url, /^otpauth:\/\/totp\//);
  assert.match(url, new RegExp(`secret=${SECRET_B32}`));
  assert.match(url, /issuer=Camxora/);
});
