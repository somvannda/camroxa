#!/usr/bin/env node
/**
 * Bucket the derived UI strings into capability areas so we can see which parts of
 * the product exist at all — including areas we have not captured in a live session.
 *
 *   node tools/suno-re/bucket-features.mjs
 */
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const REPO = process.cwd();
const source = JSON.parse(
  readFileSync(join(REPO, "docs/studio/reference/ui-strings.json"), "utf8")
);

const BUCKETS = {
  "Transport & timing": /metronome|bpm|tempo|time signature|playhead|loop|bar\b|beat\b|count.?in|tick|swing|quantiz|tap tempo|transport/i,
  "Time selection": /selection|select (all|time)|extend selection|delete time|duplicate time|insert time|time range|ripple/i,
  "Clip editing": /clip|crop|fade|split|trim|reverse|speed|stretch|pitch|gain|normalize|silence|consolidat|bounce|render/i,
  "Take lanes": /take|alternate|comp(ing)?\b|lane/i,
  "Track & mixer": /track|mute|solo|arm|fader|pan\b|send|bus|master|limiter|compress|eq\b|filter|insert|plugin|preset|sidechain|reverb|delay|chorus/i,
  "MIDI & instruments": /midi|note|piano roll|octave|velocity|chord|arpegg|arp\b|synth|instrument|drum machine|sampler/i,
  "Export & download": /export|download|wav|mp3|midi file|bundle|stem download|render mixdown/i,
  "Stems & generation": /stem|extend|cover|remaster|mashup|replace section|add vocals|add instrumental|persona|upload/i,
  "Project & versions": /project|version|revision|duplicate|archive|rename|save|autosave|restore|fork/i,
  "Library": /library|liked|playlist|workspace|upload|search|filter|sort/i,
  "Collaboration": /collab|share|invite|comment|presence|cursor|ably|realtime|permission|access/i,
  "Lyrics": /lyric|alignment|aligned|word|line\b|cowriter/i,
  "Errors & validation": /failed|error|cannot|can't|unable|invalid|timed out|not allowed|required|too (many|long|large)|infring/i,
  "Onboarding & help": /learn|tutorial|what's this|getting started|hint|tooltip|tour|guide/i,
};

const buckets = Object.fromEntries(Object.keys(BUCKETS).map((key) => [key, new Set()]));
for (const { text } of source.strings) {
  if (text.length > 80) continue;
  for (const [name, pattern] of Object.entries(BUCKETS)) {
    if (pattern.test(text)) buckets[name].add(text);
  }
}

const lines = [
  "# Feature areas derived from shipped strings",
  "",
  `Source: ${source.chunks} chunks (${source.mode}), ${source.uniqueStrings} unique strings.`,
  "",
  "> Derived labels only. Presence of a label proves the surface exists somewhere;",
  "> it does not prove the behaviour. Items marked **new** are not yet in the inventory.",
  "",
  "| Area | Candidate strings |",
  "|---|---|",
  ...Object.entries(buckets).map(([name, set]) => `| ${name} | ${set.size} |`),
  "",
];

for (const [name, set] of Object.entries(buckets)) {
  const items = [...set].sort();
  lines.push(`## ${name}`, "", ...[...items].slice(0, 120).map((text) => `- ${text}`), "");
}

writeFileSync(join(REPO, "docs/studio/reference/derived-features.md"), lines.join("\n"));
console.log(
  JSON.stringify(
    Object.fromEntries(Object.entries(buckets).map(([name, set]) => [name, set.size]))
  )
);
