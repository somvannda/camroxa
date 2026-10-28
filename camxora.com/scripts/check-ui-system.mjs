#!/usr/bin/env node
/**
 * Design-system guard for the `.s-*` surfaces (Create + Library).
 * See DESIGN_SYSTEM.md. Fails on type sizes or control heights that drift
 * from the documented scales, and on raw hex colors in the `.s-*` block.
 *
 * Run: npm run check:ui
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const file = resolve(process.cwd(), "app/globals.css");
const source = readFileSync(file, "utf8");
const start = source.indexOf(".s-page{");
if (start < 0) {
  console.error("check:ui — could not find the `.s-page{` block in app/globals.css");
  process.exit(1);
}

const body = source.slice(start);
const offset = source.slice(0, start).split("\n").length; // 1-based line of `.s-page`

const TYPE_SCALE = new Set(["11px", "12px", "13px", "14px", "15px", "16px", "18px", "22px", "24px", "26px", "28px", "30px", "32px"]);
const CONTROL_HEIGHTS = new Set(["24", "26", "28", "30", "32", "34", "36", "40", "42", "44", "46", "48"]);
const CONTROL_SELECTOR = /\.s-(btn|pager|segment|attach|create-btn|rail-action-grid|workspace|add-btn|sec-toggle|selectbox|rail-card-head)/;

const problems = [];

body.split("\n").forEach((line, index) => {
  const lineNo = offset + index;
  const font = line.match(/font-size:\s*([\d.]+px)/);
  if (font && !TYPE_SCALE.has(font[1])) {
    problems.push(`${file}:${lineNo}  font-size:${font[1]} is off-scale (allowed: ${[...TYPE_SCALE].join(", ")})`);
  }
  const height = line.match(/[^-]height:\s*(\d+)px/);
  if (height && CONTROL_SELECTOR.test(line) && !line.includes(".icon") && !line.includes("svg") && !CONTROL_HEIGHTS.has(height[1])) {
    problems.push(`${file}:${lineNo}  control height ${height[1]}px is off-scale (allowed: ${[...CONTROL_HEIGHTS].join(", ")})`);
  }
});

const hexes = [...body.matchAll(/#[0-9a-fA-F]{3,8}\b/g)].map((m) => m[0]);
const allowedHexes = new Set(["#070a13", "#0f1322", "#181f36", "#222a45", "#a855f7", "#7c3aed", "#b91c1c", "#fb9b85", "#faed87", "#aefc76", "#91c6ff", "#101012", "#fd429c", "#f4f5fb", "#c9cde0", "#8b90a6", "#6f748a", "#52d17c", "#60a5fa", "#1c1c1f", "#dc2626", "#ded5ff", "#efe9ff", "#fecaca", "#0a0d18", "#0a0d18", "#ffffff", "#fff", "#000", "#0b0716", "#3a3a40", "#2e2e33"]);
const strayHexes = [...new Set(hexes.filter((hex) => !allowedHexes.has(hex)))];
if (strayHexes.length) {
  problems.push(`${file}  raw hex outside the token palette: ${strayHexes.join(", ")}`);
}

if (problems.length) {
  console.error("check:ui — design-system violations found:\n");
  for (const problem of problems) console.error(`  ${problem}`);
  console.error(`\n${problems.length} problem(s). See DESIGN_SYSTEM.md.`);
  process.exit(1);
}

console.log("check:ui — .s-* type scale, control heights and palette are compliant.");
