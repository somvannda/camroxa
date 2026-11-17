import fs from "node:fs";
import path from "node:path";

const dir = path.resolve("docs/studio/reports/evidence-w5c");
const files = fs
  .readdirSync(dir)
  .filter((name) => name.startsWith("results-") && name.endsWith(".json"))
  .sort();

const ansi = /\u001b\[[0-9;]*m/g;
const rows = [];
for (const file of files) {
  const content = JSON.parse(fs.readFileSync(path.join(dir, file), "utf8"));
  for (const row of content) rows.push(row);
}
rows.sort((a, b) => Number(a.id.split("-")[1]) - Number(b.id.split("-")[1]));

const curated = {
  "C-08":
    "Two paths measured. Playwright's synthetic `Control+Shift+,` reports `key=\",\"` and opens Studio Settings; a hardware `keydown` with the value a US keyboard actually sends for Shift+Comma (`key=\"<\"`, `code=\"Comma\"`) opens nothing. The handler compares `event.key !== \",\"`, so the documented accelerator is dead on a real keyboard. — `C-08.png`",
  "C-11":
    "With `POST /studio/projects` delayed then aborted, the menu is already closed (every row calls `setOpen(false)` before its action) and **no error renders anywhere**: 0 `.se-dialog-error`, no toast, 0 disabled rows observed. A failed menu action is silent. — `C-11.png`",
  "C-35":
    "✕ closes the panel correctly (that half passes), but the visible note reads `Projects are saved automatically`; the sentence the row quotes (`Restoring replaces the arrangement and reloads the editor.`) does not exist in the tree (grep: 0 hits). — `C-35.png`",
  "C-47":
    "**BLOCKED / ENVIRONMENT.** Real push: `The Suno Studio mirror did not accept this project.` (the local mirror refuses a localhost callback — W4 §1.1; `readiness` also reports `musicapi:false`). With the platform result mocked to `Queued`, the dialog renders `Queued — Suno picks it up in the background.`, so the sentence path itself is sound. — `C-47-1689x1277.png`",
  "C-48":
    "Note renders once a push result carries `skipped_clips`: `2 clips stay local: no Suno asset yet.` (result supplied by the same mocked push as C-47; the real mirror returns no result at all).",
  "C-76":
    "`Split on Transients` opened with `No transients found in this clip.` — no `Finding transients…`, no split, clip count stayed 5. The negative branch is correct product copy; the fixture WAV (`/seed/demo-loop.wav`) has no detectable onsets, so the split path is unproven. — `C-76.png`",
  "C-109":
    "`Rename track` focuses the inline field (✓) but leaves the caret at the end (`selectionStart=5`, `selectionEnd=5`, length 5) — the current name is **not** selected as the row requires. Enter/Escape/blur all behave. — `C-109.png`",
  "C-130":
    "Clicking the group chip leaves `aria-pressed=false`: only the last member collapses. `groupsInUse` iterates `members.forEach(track => onUpdateTrack(track.id, {collapsed: next}))`, and `updateTrack` builds `tracks.map(...)` from the render's `tracks` snapshot (`StudioEditorShell.tsx:2544`), so each call overwrites the previous one. — `C-130.png`",
  "C-196":
    "0 `.studio-sync-dot` on the home cards. The list payload from `GET /studio/projects` has no `sync` object at all (checked through the API: `sync` absent on every item), and `StudioHome.tsx:412` renders the dot only `project.sync ? …`. The five mirror states are therefore unreachable from My Projects. — `C-196.png`",
};

const lines = ["| ID | Verdict | Evidence (measured) |", "|---|---|---|"];
for (const row of rows) {
  const raw = `${row.evidence}${row.detail ? ` — ${row.detail}` : ""}`
    .replace(ansi, "")
    .replace(/expect\(received\)[\s\S]*$/m, "")
    .replace(/\s+/g, " ")
    .trim();
  const evidence = (curated[row.id] ?? raw).replace(/\|/g, "\\|");
  lines.push(`| ${row.id} | **${row.verdict}** | ${evidence} |`);
}
fs.writeFileSync(path.join(dir, "rows.md"), lines.join("\n"), "utf8");

// Drop screenshots left over from earlier iterations of rows that now pass, and keep the
// failing rows' shots plus the deliberate reference frames.
const keep = new Set([
  "C-08", "C-11", "C-35", "C-47", "C-76", "C-109", "C-130", "C-196",
  "C-01-1689x1277", "C-13-1689x1277", "C-21-1689x1277", "C-31-1689x1277", "C-43-1689x1277",
  "C-46-1689x1277", "C-47-1689x1277", "C-64-1689x1277", "C-83-1689x1277", "C-99-1689x1277",
  "C-103-1689x1277", "C-108-1689x1277", "C-117-1689x1277", "C-122-1689x1277",
  "C-128-1689x1277", "C-132-1689x1277", "C-135-1689x1277", "C-139-1689x1277",
  "C-140-1689x1277", "C-152-1689x1277", "C-170-1689x1277", "C-177-1689x1277",
  "C-178-1689x1277", "C-182-1689x1277", "C-185-1689x1277", "C-187-1689x1277",
  "C-192-1689x1277", "C-197-1689x1277", "C-198-1689x1277", "C-199-1689x1277",
  "C-204-1689x1277", "C-205-1689x1277",
]);
let removed = 0;
for (const name of fs.readdirSync(dir)) {
  if (!name.endsWith(".png")) continue;
  const base = name.replace(/\.png$/, "");
  if (keep.has(base)) continue;
  fs.unlinkSync(path.join(dir, name));
  removed += 1;
}
console.log(`rows ${rows.length}; screenshots removed ${removed}`);
