# Residual verification plan — “everything, pixel by pixel, end to end”

**Date:** 2026-11-17
**Status:** active
**Owner:** session manager
**Base:** `origin/main` `e04e0ac3`

The clone definition is satisfied, but that contract proves **coverage, geometry and
strings** — not that every provider path still works and not that every screen is
pixel-identical. This plan closes the six gaps named in the 2026-11-16 hand-over.

Nothing here deploys. Production stays at `985ccf00` until explicitly released.

> **Status 2026-11-17:** D1 **PASS** (3,500 pytest) · D2 **PASS** (185/2 on the real-mirror
> commit; 0×5xx) · D3 **PASS with three recorded divergences** (W9b re-adjudication; see
> `CLONE_DEFINITION.md` §5) · D4 **READY, blocked on the cap** (14 rows / 188 credits; all 14
> preconditions pass with a public callback tunnel — see
> `reports/2026-11-17-provider-matrix-dry-run.md`) · D5 **DONE** (demo and MIDI
> overview shipped; other two recorded) · D6 **PASS** (509/510 checks; one row blocked by
> the local mirror; nine product defects fixed with regressions — see
> `docs/studio/reports/2026-11-17-residual-results.md`).

---

## 1. Definition of done

| # | Criterion | Evidence required |
|---|---|---|
| **D1** | Backend green after the refresh-backoff change | full `platform_api/tests` ≥ 3,479 passed, `musicapi` unit 198, ruff/black clean |
| **D2** | Full browser suite green **with the real mirror live** (`musicapi` + worker + moto + API token) | 185 passed / 2 skipped, no 5xx in the API log for the run, readiness all ✓ except the callback |
| **D3** | Every one of the **73** reference screens has an automated pixel verdict | `scripts/pixel-diff.mjs` report with one of: **SURFACE PASS** (crop/same-surface frame, ≤0.2 % differing pixels), **STRUCTURAL PASS** (whole-viewport frame: captured controls at the same relative positions ±2 px, non-brand diff reported), **STATE** (recapture needed), or **RECORDED GAP** (no reference frame exists). The 14 previously “cannot judge” screens captured first. |
| **D4** | Every provider operation works end to end, live | ids + status recorded for: generate → stems (2 and 12) → persona → cover → extend → remaster → vocals → instrumental → mashup → replace → bounce/upload → export WAV/MP3 |
| **D5** | The four absences are decided, not implied | each either built and merged, or recorded in `CLONE_DEFINITION.md` §5 with your sign-off |
| **D6** | A second, independent manual walkthrough | new agent, different from Agent A, covering every plugin parameter and three viewports, with PASS/FAIL per control |

D4 spends real provider credits and **needs explicit approval** before it runs. Everything
else is free.

---

## 2. Workstreams

| WS | Work | Owner | Needs | Artifact |
|---|---|---|---|---|
| **W0** | This plan, staffing, consolidation, final verdict | manager | — | this doc + `RESIDUAL_RESULTS.md` |
| **W1** | Full backend suite after the backoff change | `qa/backend-residual` | no servers | report + counts |
| **W2** | Pixel harness + diff of existing 53 paired captures | `qa/pixel-harness` | no servers | `scripts/pixel-diff.mjs`, diff report |
| **W3** | Capture the 14 “cannot judge” screens at reference viewports | `qa/capture-cj` | stack on `:3103` | new `ours-*.png` + PAIRING updates |
| **W4** | Full e2e with the **real mirror** | `qa/e2e-real-mirror` | full stack incl. `musicapi` | run log + API log excerpt |
| **W5** | Independent manual walkthrough (params + viewports) | `qa/manual-deep` | full stack | report + screenshots |
| **W6** | Provider matrix (live, paid) | `qa/provider-matrix` | approval + budget + tunnel | ids + status table |
| **W7** | Absence decisions (clip-rail header, MIDI overview, demo tile, tutorial tile) | manager + you | W2 report | decisions in `CLONE_DEFINITION.md` |

---

## 3. Sequencing (waves)

**Wave 1 — no contention (start now)**
- W1 backend suite
- W2 pixel harness + diff (CPU only)
- W0 plan committed

**Wave 2 — one stack owner at a time**
- W4 first (owns `:3103`); W3 and W5 queue behind it
- Reason: the host kills long-lived children and two full suites starve each other; the
  reliable pattern is start-stack-and-run in one shell lifetime.

**Wave 3 — paid, gated**
- W6 only after you approve a credit budget. The tunnel and provider env are required:
  `PLATFORM_SUNO_API_BASE_URL=http://127.0.0.1:4003`,
  `PLATFORM_STUDIO_INTERNAL_TOKEN`, a public `PLATFORM_SUNO_CALLBACK_BASE_URL`
  (`cloudflared tunnel --url http://127.0.0.1:8100`), worker running,
  `credits_only_v3_charge=true`, and the platform key present in `musicapi.api_keys`.

**Wave 4 — consolidation**
- W7 decisions, then `RESIDUAL_RESULTS.md` with a verdict per D1–D6 and a single verdict:
  *claimable* or *remaining gaps listed*.

---

## 4. Method per workstream

### W2 — pixel harness (delivered 2026-11-17)
- Decode PNG/JPEG with `pngjs` + `pixelmatch` + `jpeg-js`; normalise to the reference frame
  with nearest-neighbour; emit diff PNGs and `summary.json`; `npm run check:pixels`.
- **Tolerance policy (measured):** an exact pixel criterion cannot apply to whole-viewport
  frames because brand and palette are allowed divergences (`CLONE_DEFINITION.md` §5); the
  smallest whole-frame delta observed is **2.37 %** (S16). Therefore:
  - **crop / same-surface frames** → ≤0.2 % differing pixels = SURFACE PASS;
  - **whole-viewport frames** → STRUCTURAL PASS: the captured controls exist at the same
    relative positions ±2 px; the pixel delta is reported with a brand/palette mask, never
    used as the sole gate;
  - a frame showing a different app state is **STATE**, not a layout defect, and must be
    recaptured (W3) before it can be judged.
- First result: 52 diffable, 21 no-frame (18 spec-only, 2 negative, 1 missing reference frame
  **S43**); delta split LAYOUT 24 · STATE 13 · STATE+LAYOUT 10 · REGION 5.

### W3 — captures and the missing reference frame
- Capture/re-shoot the 13 screens whose frames show the wrong state, plus the 14 “cannot
  judge” screens, at reference viewports; update `PAIRING.json` (anchors/`sharedWith`) and
  re-run `check:clone`.
- **S43 has no reference frame at all.** Attempt to capture it read-only from the live Suno
  session (`node scripts/dev/suno-session.cjs --probe`, then a scripted screenshot); if the
  session is unavailable, record S43 as a corpus gap rather than inventing a frame.

### W4 — real-mirror e2e
- Start moto + bucket, platform API (sandbox DB, token, moto storage, Suno base →
  `:4003`), `musicapi`, worker, web; verify `/studio/readiness` shows storage/token/musicapi ✓.
- Run the full suite; grep the API log for 5xx during the run; record suite duration.

### W6 — provider matrix
- One disposable project per operation; record provider ids; never point a seeded task at
  another user's asset.
- Budget: costs read from the `pricing` table at run time; stop between operations if the
  spend exceeds the approved cap. Nothing runs without the cap.

---

## 5. Acceptance report format

`docs/studio/reports/2026-11-17-residual-results.md`:

- one row per criterion D1–D6 with PASS / FAIL / BLOCKED, the command or evidence, and the
  timestamp;
- a list of every remaining delta, classified **layout / state / absence / provider**;
- the final verdict sentence, which may only be “pixel-for-pixel clone verified” if D1–D6
  are all PASS.

---

## 6. Risks

| Risk | Mitigation |
|---|---|
| Host reaps long-lived processes | start stack and run workload in one shell lifetime (proven pattern) |
| Shared sandbox DB mutates under tests | note data-dependent failures; retry once; prefer API-seeded fixtures |
| Provider rate limits / invalid session | run W6 last, with backoff between operations and the ids recorded |
| Capture state drift | W3 scripts the state explicitly and re-runs `check:clone` |
| Pixel tool false positives | tolerance is documented and reported per screen; every DELTA links a diff image |

---

## 7. Decisions requested from you

1. **W6 budget:** approve a credit cap (suggested: one operation each, 12 operations; cap at
   the pricing table's per-op cost × 14 for retries). Without this, D4 stays BLOCKED.
2. **W7 absences:** default proposal — build the **MIDI overview strip** (real value), accept
   the clip-rail header as our layout, accept **Video Tutorial** as the recorded absence
   (dropped channel). **Drum & Bass Demo** is no longer an absence: it ships from our own
   seed loop (`docs/studio/CLONE_DEFINITION.md` §5). Tell me if you want any of those changed.
