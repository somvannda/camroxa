# W11 — mojibake repair in shipped strings and comments

**Date:** 2026-11-17
**Workstream:** W11 (residual verification)
**Agent:** W11, branch `fix/mojibake`, worktree
`C:\Users\Kong Somvannda\AppData\Local\Temp\camxora-res-moji`
**Base:** `origin/main` @ `b3d718f45d2fd5ac13989fb730b0cf4b8a31ca32` — *"feat(studio): twenty clip
colours, a default Audio Track, and a Learn menu that is actually visible"*

**Method:** text repair only. No server started, no port bound, no deploy, no push, no
provider call. `G:\Developments\Projects\Camxora` was not touched. Playwright was **not** run.

**Toolchain:** Node v24.13.0 · TypeScript 5 (`tsc --noEmit`) · Vitest · `npm ci` (272 packages)
to populate the fresh worktree.

---

## 1. Summary

The scan found pre-existing UTF-8-read-as-CP1252 mojibake in **five** files. All of it was in
text content: user-visible copy, `title`/`placeholder`/`aria` strings, status lines, comments and
two CSS `content:` values. **100 corrupted glyph sequences across 99 lines** were restored.

| File | Lines changed | Substitutions | Kind |
|---|---|---|---|
| `camxora.com/components/CreateStudio.tsx` | 40 | 40 | user-visible copy, placeholders, comments |
| `camxora.com/components/StudioEditorView.tsx` | 37 | 37 | status lines, `title`, `placeholder`, inline `·` separators |
| `camxora.com/components/LibraryView.tsx` | 1 | 1 | user-visible copy |
| `camxora.com/app/globals.css` | 6 | 6 | comments + 2 CSS `content:` values |
| `camxora.com/tests/e2e/studio-pixel.spec.ts` | 15 | 16 | comments only (U+FFFD, hand-reconstructed) |
| **Total** | **99** | **100** | |

Zero mojibake signatures remain in the scoped files, and the **ASCII skeleton of every file is
byte-identical to `HEAD`** — no logic, selector, attribute, key, URL or class name moved (§4).

**Headline user-visible win:** the Create page no longer renders `Uploading videoâ€¦` and friends;
it renders `Uploading video…`. In total **56 ellipses, 13 em dashes, 2 en dashes, 1 curly quote
pair, 8 middle dots, 2 arrows and 2 minus signs** now render as intended.

---

## 2. What the corruption actually was

Two distinct failures, both repaired with the byte-exact inverse:

1. **Single-encoded** — UTF-8 bytes decoded as CP1252 once. `…` (E2 80 A6) became
   `â` + `€` + `¦`. In the source these look like `â€¦`, `â€”`, `Â·`, `Ã©`.
2. **Double-encoded** — the same round trip applied twice, which is how
   `Ã¢â‚¬â€\u009D` (8 codepoints) came to stand for a single em dash and `Ã¢â‚¬â€œ` for an en
   dash. Applying the single-encoded table first would have shredded these into `Ã¢`, so
   longest-first ordering was mandatory.

Codepoint-level detail matters for the ambiguous-looking cases:

| In-bytes sequence | Codepoints in the file | Intended |
|---|---|---|
| `â€¦` | U+00E2 U+20AC U+00A6 | `…` |
| `â€”` | U+00E2 U+20AC **U+201D** | `—` |
| `â€“` | U+00E2 U+20AC **U+201C** | `–` |
| `â€œ` / `â€<9D>` | U+00E2 U+20AC U+0153 / U+009D | `“` / `”` |
| `Â·` | U+00C2 U+00B7 | `·` |
| `Ã¢â‚¬â€<9D>` | U+00C3 U+00A2 U+00E2 U+201A U+00AC U+00E2 U+20AC U+009D | `—` |
| `Ã¢â‚¬â€œ` | … U+20AC U+0153 | `–` |
| `â†’` | U+00E2 U+2020 U+2019 | `→` |
| `âˆ’` | U+00E2 U+02C6 U+2019 | `−` (U+2212) |

The last two were **not** in the scan's signature list (`â€|Ã|Â`) and surfaced only when the
repair pass was re-run with a general detector (§3.2). Both are user-visible: `Admin â†’ Key
Pool`, `Library â†’ Trash`, and the MIDI octave/transpose buttons that read `âˆ’` / `âˆ’12`.

---

## 3. Files, lines and the mapping actually applied

### 3.1 Substitutions per file

`CreateStudio.tsx` — 40 lines:

| N | From | To |
|---|---|---|
| 32 | `â€¦` | `…` |
| 5 | `â€”` | `—` |
| 2 | `â†’` | `→` |
| 1 | `â€œ` | `“` |
| 1 | `â€<9D>` | `”` |

Representative lines (the Create page copy users actually read):

| Line | Before | After |
|---|---|---|
| 1512 | `Remove the attached clip first â€” one video at a time.` | `… first — one video …` |
| 3718 | `<b>Uploading videoâ€¦</b>` | `<b>Uploading video…</b>` |
| 4988 | `"Loadingâ€¦"` | `"Loading…"` |
| 5289 | `Choose a playlist â€” its track styles will be merged into Styles.` | `… playlist — its …` |
| 5420 | `{…}â€¦ status: {audioStatus …}` | `…}… status: …` |
| 6391 | `00:00 â€” {…}` | `00:00 — {…}` |
| 6477 | `â€œ{voicePhraseText}â€<9D>` | `“{voicePhraseText}”` |
| 6671 | `placeholder="Describe genre … vocal styleâ€¦"` | `… vocal style…"` |

`StudioEditorView.tsx` — 37 lines:

| N | From | To |
|---|---|---|
| 23 | `â€¦` | `…` |
| 6 | `Â·` | `·` |
| 5 | `â€”` | `—` |
| 2 | `âˆ’` | `−` |
| 1 | `â€“` | `–` |

Notable: `6190`/`6194`/`6253` inline price separators `Â·` → `·`; `6748`
`project.tags.join(" Â· ")`; `6442` the loop-range label
`` `${Math.round(loopStart)}â€“${Math.round(loopEnd)}s` `` → `–`; `5509`/`5574` the MIDI
buttons `âˆ’` / `âˆ’12` → `−` / `−12` (U+2212, matching the ASCII `+` / `+12` partners and the
`−` already used in `StudioHeader.tsx` and `lib/studio-clip-audio.ts`).

`LibraryView.tsx` — 1 line: `1417` `Loading Trashâ€¦` → `Loading Trash…`.

`app/globals.css` — 6 lines:

| N | From | To | Where |
|---|---|---|---|
| 2 | `Ã¢â‚¬â€<9D>` | `—` | comments (866 "curved liquid glass buttons — static", 3728 "READABILITY PASS —") |
| 1 | `Ã¢â‚¬â€œ` | `–` | 3729 "controls 30–36" |
| 1 | `â€”` | `—` | 1140 comment |
| 2 | `Â·` | `·` | 2179/2205 `::before{content:"·"}` (CSS `content:` values) |

`tests/e2e/studio-pixel.spec.ts` — 15 lines, 16 U+FFFD, **reconstructed by hand** because
U+FFFD on disk is irreversible. Sources of truth used: the sibling specs already spell the
section marker as `§` (`studio-library.spec.ts:6` "spec §19.1/§19.2", `studio-learn.spec.ts:6`
"reference §7/§38"), and `docs/studio/SUNO_STUDIO_IMPLEMENTATION_SPEC.md` uses `×` for
dimensions and `≈` for measured approximations ("controls at y ≈ 1124–1157").

| Line | Before | After | Evidence |
|---|---|---|---|
| 7 | `spec �1.` | `spec §1.` | sibling specs use `§` |
| 9 | `(1689�1277, DPR 1)` | `(1689×1277, DPR 1)` | `capture-screens.mjs:1265` writes `1689×1277`; spec `1689 × 1277` |
| 48 | `// �1 frame.` | `// §1 frame.` | section reference |
| 55 | `// �52.1 row rhythm.` | `// §52.1 row rhythm.` | section reference |
| 60 | `controls 24�24` | `controls 24×24` | control size, not a range |
| 115 | `// �4 ruler:` | `// §4 ruler:` | section reference |
| 141 | `// �2 header: … at x�115` | `// §2 header: … at x≈115` | spec H-01 places the project chip at x 115; measured, hence `≈` (matches `y ≈ 1124` style) |
| 171 | `// �44.3 ruler pitch:` | `// §44.3 ruler pitch:` | section reference |
| 178 | `// �4 playhead:` | `// §4 playhead:` | section reference |
| 194 | `// �4 bottom time ruler:` | `// §4 bottom time ruler:` | section reference |
| 260 | `// �7.1:` | `// §7.1:` | section reference |
| 582 | `// �7.1:` | `// §7.1:` | section reference |
| 626 | `29 px head � expand` | `29 px head — expand` | parenthetical dash in an English sentence |
| 1282 | `169�64 tiles` | `169×64 tiles` | tile dimensions |
| 1592 | `// �19.1:` | `// §19.1:` | section reference |

### 3.2 Tooling used (and kept)

Because the file set is small and the sequences are byte-exact, the repair was applied by a
deterministic, longest-first substitution table rather than 100 hand edits — no edit could then
land in the wrong place.

A small gate was added so the defect cannot silently return:

```
node scripts/check-mojibake.mjs            # app, components, lib, tests → 302 files
node scripts/check-mojibake.mjs <paths>    # explicit files/directories
```

`camxora.com/scripts/check-mojibake.mjs` reports `â€œ â€<9D> â€” â€“ â€¦ â€™ â€ Â· Â° Ã Â` and
`U+FFFD`, name-the-label per hit, and exits 1 on any finding. It skips itself (its own
documentation must quote the signatures) and is **not** wired into an npm script, so it cannot
block CI by surprise. It was sanity-checked by scanning a deliberately corrupted probe file
(`"Uploading videoâ€¦"` / `cafÃ©`) — it reported 3 signatures and exited 1.

---

## 4. Proof the repair changed no behaviour

The repair was verified three ways, all cheap and offline.

**4.1 Signature scan — clean.** `node scripts/check-mojibake.mjs` over the five scoped files:
`clean: no mojibake signatures in 5 file(s).` Whole source tree (`app`, `components`, `lib`,
`tests`): `clean: no mojibake signatures in 302 file(s).` Zero `â€`, `Ã`, `Â` and zero U+FFFD.

**4.2 ASCII-skeleton invariance — identical.** For each file, `git show HEAD:<file>` and the
working copy were both stripped of every non-ASCII codepoint and compared:

```
OK   camxora.com/components/CreateStudio.tsx: ASCII skeleton identical (only non-ASCII glyphs changed)
OK   camxora.com/components/StudioEditorView.tsx: ASCII skeleton identical (only non-ASCII glyphs changed)
OK   camxora.com/components/LibraryView.tsx: ASCII skeleton identical (only non-ASCII glyphs changed)
OK   camxora.com/app/globals.css: ASCII skeleton identical (only non-ASCII glyphs changed)
OK   camxora.com/tests/e2e/studio-pixel.spec.ts: ASCII skeleton identical (only non-ASCII glyphs changed)
RESULT: no ASCII content changed in any file
```

This is the strongest statement available for "text only": every identifier, JSX tag, prop,
selector, URL, class name and brace in the five files is bit-identical to `HEAD`. (The comparison
normalises CRLF→LF first, because `core.autocrlf=true` stores LF blobs and checks out CRLF; the
working files were rewritten with their original CRLF endings intact — the diff is
addition/deletion paired, so no line endings were converted.)

**4.3 General detector — clean.** A reverse-CP1252 → UTF-8 decoder (not limited to the known
signatures) found exactly the 4 runs from §2's last two rows before they were fixed, and
**zero** afterwards in the five files.

**4.4 Full app tree detector.** The same general detector over the whole repository found no
further real mojibake in `camxora.com/` source. The only hits were the `×½` / `×2` / `×–11×`
speed and range labels (`StudioAudioEditor.tsx:364`, `studio-audio-editor.test.tsx:169,181`,
`docs/studio/PIXEL_PARITY.md`, `PROJECT_PROGRESS.md` and two reports) — those are legitimate
multiplication signs, correctly *not* touched. The detector decodes `×½` (D7 BD) as U+05BD, a
classic false positive of this technique.

---

## 5. Verification

| # | Command (in `camxora.com/`) | Result |
|---|---|---|
| 1 | `npm run typecheck` (`tsc --noEmit`) | **clean**, no output |
| 2 | `npx vitest run` | **51 files, 387 tests passed**, 0 failed (9.0 s) |
| 3 | `npm run check:ui` | **compliant** — ".s-* type scale, control heights and palette are compliant." |
| 4 | `node scripts/check-mojibake.mjs` (scoped) | **clean**, 5 files |
| 5 | `node scripts/check-mojibake.mjs` (tree) | **clean**, 302 files |

Playwright was not run, per instructions. `npm ci` was needed first because the worktree was
fresh (272 packages, 20 s) — no lockfile change.

---

## 6. Unresolved cases

**In scope: none.** Every corrupted sequence in the five scoped files was unambiguous and is
fixed; nothing was left behind for want of context.

**Out of scope, found by the same scan** (not touched — separate trees/owners, and the brief
scopes this pass to the five files above). Line counts are lines containing a signature:

| File | Lines | Notes |
|---|---|---|
| `platform_api/routers/users.py` | 10 | real: `â€”` in OpenAPI route `description`s (403/Forbidden) and comments — **user-visible in `/docs`** |
| `admin_portal/src/pages/mail/index.tsx` | 9 | real: `â€”` date fallbacks, `Loadingâ€¦`, `Savingâ€¦`, `Â·` (admin UI copy) |
| `camxora_python/features/video/lib/playlist_stage.py` | 4 | real; legacy PyQt6 tree |
| `docs/DEPLOYMENT_OPERATIONS.md` | 21 | real docs mojibake |
| `platform_api/CHANGELOG.md` | 56 | real docs mojibake |
| `docs/studio/SUNO_STUDIO_IMPLEMENTATION_SPEC.md` | 10 | real; the parity source of truth — worth a follow-up |
| `docs/studio/PROJECT_DECISIONS.md` | 17 | real |
| `docs/changelog/2026-08-04-…-media-404.md`, `2026-08-22-…`, `docs/credits-only-test-results.md` | 5 / 3 / 3 | real docs mojibake |
| `platform_api/tests/test_deploy_hygiene_alembic.py`, `test_locked_migration_entrypoint.py` | 1 / 1 | real, in docstrings |
| `camxora.com/UI_AUDIT.md` | 11 | U+FFFD only — text already lost, needs re-authoring, not a mapping |
| `music_web/src/lib/vendor/mpg123/*.js` | 118 | **not a defect**: vendored minified Emscripten, third-party, untouched |

Recommended follow-up: one batch over the docs/markdown set (mechanical, same table) and a
separate small pass for `platform_api/routers/users.py` + `admin_portal` mail page, both of
which put the mojibake in front of users. `UI_AUDIT.md`'s U+FFFD needs rewriting by hand.

---

## 7. Diff footprint

```
camxora.com/app/globals.css                 | 12 +++---
camxora.com/components/CreateStudio.tsx     | 80 +++++++++++++-------------
camxora.com/components/LibraryView.tsx      |  2 +-
camxora.com/components/StudioEditorView.tsx | 74 +++++++++++-----------
camxora.com/tests/e2e/studio-pixel.spec.ts  | 30 +++++-----
camxora.com/scripts/check-mojibake.mjs      | new (gate)
```

Commit: `fix(studio): repair CP1252 mojibake in Create, Library and Studio copy` on branch
`fix/mojibake` — `85c47c29` (code) + `docs(studio): report the mojibake repair and add a scan
gate` (this report and `scripts/check-mojibake.mjs`). Working tree left clean.
