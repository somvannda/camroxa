import { test } from "node:test";
import assert from "node:assert/strict";

import {
  alignedLinesToLrc,
  alignedWordsToLrc,
  formatLrcTime,
  lrcToSrt,
  parseLrcLines,
  parseLrcTimestamp,
} from "../src/lrc.js";

test("formatLrcTime renders [mm:ss.xx]", () => {
  assert.equal(formatLrcTime(0), "[00:00.00]");
  assert.equal(formatLrcTime(65.5), "[01:05.50]");
  assert.equal(formatLrcTime(-5), "[00:00.00]");
});

test("parseLrcTimestamp handles 1/2/3-digit fractions", () => {
  assert.equal(parseLrcTimestamp("01", "05", "5"), 65.5);
  assert.equal(parseLrcTimestamp("01", "05", "50"), 65.5);
  assert.equal(parseLrcTimestamp("01", "05", "500"), 65.5);
});

test("alignedLinesToLrc needs at least two non-empty lines", () => {
  assert.equal(alignedLinesToLrc([{ text: "one", startS: 1 }]), "");
  assert.equal(
    alignedLinesToLrc([
      { text: "one", startS: 1 },
      { text: "two", startS: 2 },
    ]),
    "[00:01.00]one\n[00:02.00]two",
  );
});

test("alignedWordsToLrc groups tokens on embedded newlines", () => {
  const words = [
    { word: "Hel", startS: 1 },
    { word: "lo\n", startS: 1 },
    { word: "World\n", startS: 2 },
  ];
  assert.equal(alignedWordsToLrc(words), "[00:01.00]Hello\n[00:02.00]World");
  assert.equal(alignedWordsToLrc([]), "");
  assert.equal(alignedWordsToLrc([{ word: "single", startS: 0 }]), "");
});

test("parseLrcLines and lrcToSrt round-trip", () => {
  const lrc = "[00:01.00]one\n[00:03.50]two";
  assert.deepEqual(parseLrcLines(lrc), [
    [1, "one"],
    [3.5, "two"],
  ]);
  const srt = lrcToSrt(lrc);
  assert.match(srt, /00:00:01,000 --> /);
  assert.match(srt, /\ntwo\n/);
  assert.equal(lrcToSrt("no timestamps here"), "");
});
