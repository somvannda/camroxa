/**
 * Unit checks for `src/lrc.ts` (no network, no deps).
 *
 * Run: `npm run test:lrc` (or `tsx scripts/test-lrc.ts`). Exits non-zero on the
 * first failed assertion so it can gate CI/deploy like the smoke scripts.
 */
import {
  formatLrcTime,
  formatSrtTime,
  parseLrcTimestamp,
  parseAlignedWordsPayload,
  alignedWordsToLrc,
  alignedLinesToLrc,
  looksLikeLrc,
  parseLrcLines,
  lrcToSrt,
} from "../src/lrc.js";

let passed = 0;

function eq(actual: unknown, expected: unknown, label: string): void {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) {
    console.error(`FAIL ${label}\n  expected: ${e}\n  actual:   ${a}`);
    process.exit(1);
  }
  passed++;
}

// formatLrcTime
eq(formatLrcTime(0), "[00:00.00]", "formatLrcTime zero");
eq(formatLrcTime(65.2), "[01:05.20]", "formatLrcTime minutes");
eq(formatLrcTime(-3), "[00:00.00]", "formatLrcTime clamps negative");

// parseLrcTimestamp
eq(parseLrcTimestamp("01", "05", "2"), 65.2, "parseLrcTimestamp 1-digit millis");
eq(parseLrcTimestamp("01", "05", "25"), 65.25, "parseLrcTimestamp 2-digit millis");
eq(parseLrcTimestamp("01", "05", "250"), 65.25, "parseLrcTimestamp 3-digit millis");
eq(parseLrcTimestamp("00", "10"), 10, "parseLrcTimestamp no millis");

// parseAlignedWordsPayload
eq(
  parseAlignedWordsPayload({ data: { alignedWords: [{ word: "a", startS: 1 }] } }),
  [{ word: "a", startS: 1 }],
  "parse alignedWords nested data",
);
eq(
  parseAlignedWordsPayload({ aligned_words: [{ word: "b", startS: 2 }] }),
  [{ word: "b", startS: 2 }],
  "parse aligned_words top-level",
);
eq(parseAlignedWordsPayload(null), [], "parse null payload");
eq(parseAlignedWordsPayload({ data: { alignedWords: "nope" } }), [], "parse non-list");

// alignedWordsToLrc — newline embedded in word marks a line break.
eq(
  alignedWordsToLrc([
    { word: "Hello ", startS: 1.0 },
    { word: "world\n", startS: 1.4 },
    { word: "Second ", startS: 3.0 },
    { word: "line\n", startS: 3.5 },
  ]),
  "[00:01.00]Hello world\n[00:03.00]Second line",
  "alignedWordsToLrc groups on newline",
);
eq(
  alignedWordsToLrc([{ word: "one line only\n", startS: 1 }]),
  "",
  "alignedWordsToLrc needs two lines",
);
eq(alignedWordsToLrc(null), "", "alignedWordsToLrc empty");
eq(
  alignedWordsToLrc([
    { word: "a", startS: 0 },
    { word: "\nb", startS: 1 },
  ]),
  "[00:00.00]a\n[00:01.00]b",
  "alignedWordsToLrc splits on leading newline",
);

// wordStart fallbacks
eq(
  alignedWordsToLrc([
    { word: "x ", start_s: 2 },
    { word: "y\n", start: 4 },
    { word: "z", startS: 6 },
  ] as never),
  "[00:02.00]x y\n[00:06.00]z",
  "alignedWordsToLrc start key fallbacks",
);

// alignedLinesToLrc
eq(
  alignedLinesToLrc([
    { text: "First", startS: 0.5 },
    { text: "  ", startS: 1 },
    { text: "Second", startS: 2.0 },
  ]),
  "[00:00.50]First\n[00:02.00]Second",
  "alignedLinesToLrc filters blanks",
);
eq(alignedLinesToLrc([{ text: "only", startS: 0 }]), "", "alignedLinesToLrc needs two");

// looksLikeLrc
eq(looksLikeLrc("[00:01.00]a\n[00:02.00]b"), true, "looksLikeLrc two tags");
eq(looksLikeLrc("[00:01.00]a"), false, "looksLikeLrc one tag");
eq(looksLikeLrc("plain lyrics"), false, "looksLikeLrc plain");
eq(looksLikeLrc(""), false, "looksLikeLrc empty");

// parseLrcLines + SRT
eq(parseLrcLines("[00:01.00]Hello\nnoise\n[00:03.50]World"), [
  [1, "Hello"],
  [3.5, "World"],
], "parseLrcLines skips non-tags");
eq(formatSrtTime(3661.5), "01:01:01,500", "formatSrtTime hours");
eq(
  lrcToSrt("[00:01.00]Hello\n[00:03.00]World"),
  "1\n00:00:01,000 --> 00:00:02,950\nHello\n\n2\n00:00:03,000 --> 00:00:08,000\nWorld\n",
  "lrcToSrt basic",
);

console.log(`lrc: ${passed} checks passed`);
