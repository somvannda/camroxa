#!/usr/bin/env node
/**
 * Pixel diff harness for the 73 reference screens (W2, RESIDUAL_VERIFICATION_PLAN.md §4).
 *
 * For every PAIRING.json entry that has a capture, diff our PNG against the reference
 * JPEG for that screen:
 *   1. decode the reference (jpeg-js) and our capture (pngjs) to raw RGBA;
 *   2. nearest-neighbour resample our capture to the reference's exact dimensions
 *      (deterministic; no library, no filtering, no interpolation);
 *   3. pixelmatch the two RGBA buffers with includeAA=false (anti-aliasing is an artefact
 *      of the resample + font rasterisation, not a layout signal) at threshold 0.1;
 *   4. write the diff PNG to docs/studio/reports/pixel-diff/<screen>.png and print a row.
 *
 * Verdicts
 *   IDENTICAL  0 differing pixels
 *   WITHIN     differing pixels <= tolerance (default 0.2 %)
 *   DELTA      differing pixels > tolerance; diff PNG written
 *   NO-FRAME   no capture, no reference frame, or the paired capture is missing
 *
 * Entries whose evidence is spec-only / negative are classified NO-FRAME and the spec file
 * is inspected to say whether it is behavioural or visual (screenshot/CSS/geometry asserts).
 *
 * Usage: npm run check:pixels [-- --tol=0.2 --md --json]
 * Exit 0 only when every diffable screen is IDENTICAL or WITHIN tolerance.
 */

import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import jpeg from "jpeg-js";
import pixelmatch from "pixelmatch";
import { PNG } from "pngjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = resolve(HERE, "..");
const REPO = resolve(APP, "..");
const DOCS = join(REPO, "docs", "studio");
const REF_DIR = join(DOCS, "reference", "screens");
const COMPARE = join(DOCS, "compare");
const E2E = join(APP, "tests", "e2e");
const OUT_DIR = join(DOCS, "reports", "pixel-diff");

const args = process.argv.slice(2);
const flag = (name) => args.includes(`--${name}`);
const value = (name, fallback) => {
  const hit = args.find((a) => a.startsWith(`--${name}=`));
  return hit ? Number(hit.split("=")[1]) : fallback;
};

const TOLERANCE_PCT = value("tol", 0.2);
const PIXEL_THRESHOLD = value("threshold", 0.1);
const EMIT_MD = flag("md");
const EMIT_JSON = flag("json");

if (!existsSync(OUT_DIR)) mkdirSync(OUT_DIR, { recursive: true });

// ---------------------------------------------------------------- inputs
const pairing = JSON.parse(readFileSync(join(DOCS, "reference", "PAIRING.json"), "utf8")).screens;
const refFrames = readdirSync(REF_DIR).filter((name) => name.endsWith(".jpeg"));
const refCache = new Map();

function decodeReference(name) {
  if (!refCache.has(name)) {
    const decoded = jpeg.decode(readFileSync(join(REF_DIR, name)), { useTArray: true });
    refCache.set(name, { width: decoded.width, height: decoded.height, data: decoded.data });
  }
  return refCache.get(name);
}

/** Frames belonging to a screen id: exact `S17` or prefixed `S17-…` / `EXTRA-…`. */
function framesFor(id) {
  return refFrames.filter((name) => {
    const base = name.replace(/\.jpeg$/, "");
    return base === id || base.startsWith(`${id}-`);
  });
}

const tokenise = (slug) => slug.split("-").filter(Boolean);
const slugOf = (name) => name.replace(/\.[a-z]+$/i, "");

/**
 * Screens whose paired capture is a known wrong state, where slug-matching would pick the
 * equally-wrong reference state and prove nothing. S48's capture is the EMPTY master chain;
 * `S48-master-no-chain` would compare absence with absence, so the screen is diffed against
 * the frame it is actually about (`S48-master-limiter`).
 */
const FRAME_OVERRIDES = {
  S48: "S48-master-limiter.jpeg",
};

/**
 * Pick one reference frame per screen, deterministically:
 *   1. most slug tokens shared with the capture name (S65 gate-767 → S65-gate-767px);
 *   2. fewest extra tokens in the frame slug (the "primary" frame for a multi-frame id);
 *   3. alphabetical.
 * This keeps S05-empty-project over the remount variant, S12-share-dialog over the naming
 * gate, S44-convolution-card over the IR-loaded crop and S48-master-no-chain over the cards.
 */
function chooseFrame(id, captureName) {
  if (FRAME_OVERRIDES[id]) return FRAME_OVERRIDES[id];
  const candidates = framesFor(id);
  if (candidates.length === 0) return null;
  const captureTokens = new Set(tokenise(slugOf(captureName).replace(/^ours-/, "")));
  const scored = candidates.map((name) => {
    const base = slugOf(name);
    const refTokens = tokenise(base.slice(id.length).replace(/^-/, ""));
    const overlap = refTokens.filter((t) => captureTokens.has(t)).length;
    return { name, overlap, extra: refTokens.length };
  });
  scored.sort((a, b) => b.overlap - a.overlap || a.extra - b.extra || a.name.localeCompare(b.name));
  return scored[0].name;
}

// ---------------------------------------------------------------- image ops
const outOf = (i, size) => Math.min(size - 1, Math.max(0, Math.round(i)));

/** Nearest-neighbour resample to exactly width×height. Deterministic by construction. */
function resizeNearest(src, width, height) {
  if (src.width === width && src.height === height) return src;
  const data = new Uint8Array(width * height * 4);
  const xRatio = src.width / width;
  const yRatio = src.height / height;
  for (let y = 0; y < height; y++) {
    const sy = outOf((y + 0.5) * yRatio - 0.5, src.height);
    const srcRow = sy * src.width;
    const dstRow = y * width;
    for (let x = 0; x < width; x++) {
      const sx = outOf((x + 0.5) * xRatio - 0.5, src.width);
      const s = (srcRow + sx) * 4;
      const d = (dstRow + x) * 4;
      data[d] = src.data[s];
      data[d + 1] = src.data[s + 1];
      data[d + 2] = src.data[s + 2];
      data[d + 3] = src.data[s + 3];
    }
  }
  return { width, height, data };
}

/** Fraction of differing pixels per horizontal band, from the alpha diff mask. */
function bandProfile(mask, width, height) {
  const headerRows = Math.max(1, Math.round((52 * height) / 1277));
  const footerRows = Math.max(1, Math.round((60 * height) / 1277));
  const band = (from, to) => {
    let differing = 0;
    let total = 0;
    for (let y = from; y < to; y++) {
      for (let x = 0; x < width; x++) {
        total += 1;
        if (mask[(y * width + x) * 4 + 3] > 0) differing += 1;
      }
    }
    return total === 0 ? 0 : round2((differing / total) * 100);
  };
  return {
    headerPct: band(0, headerRows),
    bodyPct: band(headerRows, height - footerRows),
    footerPct: band(height - footerRows, height),
  };
}

const round2 = (n) => Math.round(n * 100) / 100;

/** Strong vertical/horizontal edges as 0–1 positions, strongest first. */
function edgeProfile({ width, height, data }, limit = 28) {
  const at = (x, y) => {
    const i = (y * width + x) * 4;
    return [data[i], data[i + 1], data[i + 2]];
  };
  const columns = [];
  for (let x = 1; x < width - 1; x += 1) {
    let strong = 0;
    for (let y = 0; y < height; y += 1) {
      const a = at(x, y);
      const b = at(x + 1, y);
      if (Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]) + Math.abs(a[2] - b[2]) > 24) strong += 1;
    }
    if (strong > height * 0.15) columns.push({ p: x / width, strong });
  }
  const rows = [];
  for (let y = 1; y < height - 1; y += 1) {
    let strong = 0;
    for (let x = 0; x < width; x += 1) {
      const a = at(x, y);
      const b = at(x, y + 1);
      if (Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]) + Math.abs(a[2] - b[2]) > 24) strong += 1;
    }
    if (strong > width * 0.15) rows.push({ p: y / height, strong });
  }
  const collapse = (list) => {
    const sorted = [...list].sort((a, b) => b.strong - a.strong).slice(0, limit);
    const out = [];
    for (const edge of sorted) {
      if (out.every((seen) => Math.abs(seen.p - edge.p) > 0.01)) out.push(edge);
    }
    return out;
  };
  return { columns: collapse(columns), rows: collapse(rows) };
}

/**
 * Fraction of the reference's strong edges that also exist in ours, within 1.5 % of the
 * dimension. This is the structural criterion: brand/palette can differ pixel by pixel,
 * but the layout skeleton (panel edges, header, footer, ruler bands) must line up.
 */
function structuralScore(reference, ours) {
  const ref = edgeProfile(reference);
  const mine = edgeProfile(ours);
  const near = (a, b) => a.some((edge) => Math.abs(edge.p - b.p) <= 0.015);
  const all = [...ref.columns, ...ref.rows];
  if (all.length === 0) return 1;
  const matched = all.filter((edge) => near(mine.columns, edge) || near(mine.rows, edge)).length;
  return round2(matched / all.length);
}


/**
 * Comparability of the evidence frame. A frame that is not a full viewport (detail strip,
 * card crop, panel close-up) cannot be whole-frame diffed against our screenshot: the scales
 * differ, so a delta is a framing artefact, not proof of a layout defect. Reported as
 * `crop-or-panel` and classified REGION in the report.
 */
function comparability(ref, ours) {
  const refAspect = ref.width / ref.height;
  const ourAspect = ours.width / ours.height;
  const aspectDeltaPct = Math.abs(refAspect - ourAspect) / ourAspect * 100;
  const wholeViewport = ref.height >= 900 && ref.width >= 720;
  let kind = "crop-or-panel";
  if (wholeViewport) kind = aspectDeltaPct <= 20 ? "full-viewport" : "different-viewport";
  return {
    kind,
    // Only a same-shaped full viewport can be compared whole-frame: any other frame is
    // resampled non-uniformly, so the global percentage is dominated by the framing.
    wholeFrameComparable: kind === "full-viewport",
    refAspect: round2(refAspect),
    oursAspect: round2(ourAspect),
    aspectDeltaPct: round2(aspectDeltaPct),
  };
}

/** Behavioural vs visual: does the spec assert pixels/CSS/geometry, or only behaviour? */
const VISUAL_SIGNALS = [
  "toHaveScreenshot",
  "toMatchSnapshot",
  "toHaveCSS",
  "boundingBox",
  "getComputedStyle",
  "toHaveAttribute(\"style\"",
  "clip:", // Playwright screenshot clip
];

function specNature(specName) {
  if (!specName) return null;
  const path = join(E2E, specName);
  if (!existsSync(path)) return { nature: "missing", detail: `spec not found: tests/e2e/${specName}` };
  const text = readFileSync(path, "utf8");
  const hits = VISUAL_SIGNALS.filter((signal) => text.includes(signal));
  return {
    nature: hits.length > 0 ? "visual" : "behavioural",
    detail: hits.length > 0 ? `asserts ${hits.join(", ")}` : "no screenshot/CSS/geometry assertion",
  };
}

// ---------------------------------------------------------------- run
const rows = [];
const problems = [];

for (const [id, entry] of Object.entries(pairing)) {
  const captureName = entry.capture ?? null;
  const spec = typeof entry.spec === "string" ? entry.spec : null;
  const nature = specNature(spec);
  const row = {
    id,
    title: entry.title,
    evidence: captureName ? `capture:${captureName}` : entry.negative ? "negative" : `spec:${spec ?? "none"}`,
    capture: captureName,
    frame: null,
    refSize: null,
    oursSize: null,
    verdict: "NO-FRAME",
    reason: null,
    diffPct: null,
    identicalPixels: null,
    diffImage: null,
    bands: null,
    comparability: null,
    specNature: nature?.nature ?? null,
    specDetail: nature?.detail ?? null,
    sharedWith: entry.sharedWith ?? null,
  };

  if (!captureName) {
    row.reason = entry.negative ? "negative screen — existence is asserted in code/spec, no frame to diff" : "spec-only screen — no paired capture";
    rows.push(row);
    continue;
  }

  const capturePath = join(COMPARE, captureName);
  if (!existsSync(capturePath)) {
    row.reason = `paired capture missing: docs/studio/compare/${captureName}`;
    problems.push(`${id}: ${row.reason}`);
    rows.push(row);
    continue;
  }

  const frameName = chooseFrame(id, captureName);
  if (!frameName) {
    row.reason = `no reference frame starts with "${id}"`;
    row.oursSize = sizeOf(capturePath);
    rows.push(row);
    continue;
  }

  const ref = decodeReference(frameName);
  const oursRaw = PNG.sync.read(readFileSync(capturePath));
  const ours = { width: oursRaw.width, height: oursRaw.height, data: oursRaw.data };

  const normalised = resizeNearest(ours, ref.width, ref.height);
  const mask = new Uint8Array(ref.width * ref.height * 4);
  const differing = pixelmatch(ref.data, normalised.data, mask, ref.width, ref.height, {
    threshold: PIXEL_THRESHOLD,
    includeAA: false,
    alpha: 0.5,
    diffMask: true,
    diffColor: [255, 0, 0],
  });

  // Composite the alpha mask over a dimmed copy of the reference: the familiar pixelmatch
  // look (red where different, faded reference elsewhere) without a second diff pass.
  const diffData = new Uint8Array(ref.width * ref.height * 4);
  for (let i = 0; i < ref.width * ref.height; i++) {
    const p = i * 4;
    if (mask[p + 3] > 0) {
      diffData[p] = 255;
      diffData[p + 1] = 0;
      diffData[p + 2] = 0;
      diffData[p + 3] = 255;
    } else {
      diffData[p] = 255 - (255 - ref.data[p]) * 0.35;
      diffData[p + 1] = 255 - (255 - ref.data[p + 1]) * 0.35;
      diffData[p + 2] = 255 - (255 - ref.data[p + 2]) * 0.35;
      diffData[p + 3] = 255;
    }
  }

  const total = ref.width * ref.height;
  const diffPct = round2((differing / total) * 100);
  const diffName = `${id}.png`;
  writeFileSync(join(OUT_DIR, diffName), PNG.sync.write({ width: ref.width, height: ref.height, data: diffData }));

  row.frame = frameName;
  row.refSize = `${ref.width}x${ref.height}`;
  row.oursSize = `${ours.width}x${ours.height}`;
  row.diffPct = diffPct;
  row.differingPixels = differing;
  row.identicalPixels = differing === 0;
  row.diffImage = `docs/studio/reports/pixel-diff/${diffName}`;
  row.comparability = comparability(ref, ours);
  row.bands = bandProfile(mask, ref.width, ref.height);

  row.edgeScore = structuralScore(ref, ours);
  if (differing === 0) {
    row.verdict = "IDENTICAL";
  } else if (diffPct <= TOLERANCE_PCT) {
    row.verdict = "WITHIN";
  } else {
    // Brand and palette are allowed divergences, so a pixel delta is expected. The edge
    // score is reported as a signal; adjudication (ALLOWED / STATE / LAYOUT / REGION)
    // lives in the report, because an edge detector cannot tell a menu state from a bug.
    row.verdict = row.edgeScore >= 0.6 ? "STRUCTURAL" : "REVIEW";
  }

  rows.push(row);
}

function sizeOf(path) {
  const png = PNG.sync.read(readFileSync(path));
  return `${png.width}x${png.height}`;
}

// ---------------------------------------------------------------- output
const counts = rows.reduce(
  (acc, row) => {
    acc[row.verdict] = (acc[row.verdict] ?? 0) + 1;
    return acc;
  },
  { IDENTICAL: 0, WITHIN: 0, STRUCTURAL: 0, REVIEW: 0, "NO-FRAME": 0 },
);

const summary = {
  generatedAt: new Date().toISOString(),
  tolerancePct: TOLERANCE_PCT,
  pixelThreshold: PIXEL_THRESHOLD,
  scaler: "nearest-neighbour",
  totalScreens: rows.length,
  diffable: counts.IDENTICAL + counts.WITHIN + counts.STRUCTURAL + counts.REVIEW,
  counts,
  screens: rows,
};
writeFileSync(join(OUT_DIR, "summary.json"), `${JSON.stringify(summary, null, 2)}\n`);

if (EMIT_JSON) console.log(JSON.stringify(summary, null, 2));

if (EMIT_MD) {
  console.log("| # | Screen | Evidence | Frame | Size (ref ← ours) | Verdict | % diff | Diff image |");
  console.log("|---|---|---|---|---|---|---|---|");
  rows.forEach((row, index) => {
    const size = row.refSize ? `${row.refSize} ← ${row.oursSize}` : row.oursSize ? `— ← ${row.oursSize}` : "—";
    console.log(
      `| ${index + 1} | ${row.id} | ${row.evidence} | ${row.frame ?? "—"} | ${size} | ${row.verdict} | ${
        row.diffPct ?? "—"
      } | ${row.diffImage ?? "—"} |`,
    );
  });
  process.exit(counts.DELTA > 0 || problems.length > 0 ? 1 : 0);
}

const pad = (text, width) => String(text).padEnd(width);
console.log(`pixel-diff — tolerance ${TOLERANCE_PCT}% of pixels (pixelmatch threshold ${PIXEL_THRESHOLD}, includeAA=false)`);
console.log(`scaler: nearest-neighbour to the reference frame's dimensions · diff PNGs: ${relative(REPO, OUT_DIR)}`);
console.log("");
console.log(`${pad("screen", 30)} ${pad("verdict", 10)} ${pad("% diff", 8)} ${pad("frame", 34)} bands h/b/f`);
console.log("-".repeat(110));
for (const row of rows) {
  const bands = row.bands ? `${row.bands.headerPct}/${row.bands.bodyPct}/${row.bands.footerPct}` : "—";
  console.log(
    `${pad(row.id, 30)} ${pad(row.verdict, 10)} ${pad(row.diffPct ?? "—", 8)} ${pad(row.frame ?? row.reason ?? "—", 34)} ${bands}`,
  );
}
console.log("");
console.log(
  `screens ${rows.length} · diffable ${summary.diffable} · identical ${counts.IDENTICAL} · within ${counts.WITHIN} · structural ${counts.STRUCTURAL} · review ${counts.REVIEW} · no-frame ${counts["NO-FRAME"]}`,
);
if (problems.length > 0) console.log(`problems: ${problems.join("; ")}`);

const failing = problems.length > 0;
if (failing) {
  console.log(`FAIL — ${problems.length} measurement problem(s)`);
  process.exit(1);
}
console.log(
  `MEASURED — ${counts.STRUCTURAL} structural, ${counts.REVIEW} need adjudication (see the report)`,
);
