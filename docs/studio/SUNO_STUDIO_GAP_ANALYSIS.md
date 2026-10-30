# SUNO STUDIO GAP ANALYSIS

Honest comparison: what the reference exposes, what we have, what is missing, and
what we deliberately do not copy.

Scoring for this document:

- **Parity** — the workflow exists and behaves comparably.
- **Partial** — exists but a meaningful part of the workflow is missing.
- **Missing** — no implementation.
- **Deliberate** — we choose not to reproduce it (with reason).

## 1. Headline

| Area | Reference surface | Ours | Verdict |
|---|---|---|---|
| Studio entry | Landing + project chooser + start-from-song | Marketing page; chooser lives inside the editor as a dialog | **Missing** (W1) |
| Arrangement editor | Multitrack, clips, fades, split, markers, zoom | Present and richer in places (automation, groups, takes) | **Parity** |
| Mixing | Per-track mix, master, FX | Present (EQ, filter, sends, dynamics, presets, master chain) | **Parity** |
| MIDI | Piano roll, MIDI instrument, keyboard | Present + Web MIDI + chord/arp | **Parity** |
| Generation in the DAW | Prompt at playhead, transforms (extend/cover/replace/remaster/stems/mashup) | Present via our provider | **Parity** (unverified E2E) |
| Export | Mix, range, stems | Present in browser + server render endpoints | **Partial** (no loudness/mastering readout) |
| Collaboration | Share links, comments, presence | Present (links, comments, presence, fork) | **Parity** (unverified E2E) |
| Library integration | Songs, liked, uploads, stems, projects | Songs + liked + upload; no stems/projects tabs | **Partial** |
| Reliability | Autosave + conflict handling | Autosave present; no conflict UX, no offline draft | **Partial** (W2) |
| Quality gates | n/a | No Studio test suite; no a11y run | **Missing** (W5) |

## 2. Detailed gaps

| # | Gap | Impact | Roadmap | Status |
|---|---|---|---|---|
| G1 | No Studio home; `/studio` is marketing | Users cannot discover, resume, or manage projects without entering the DAW | W1.1–W1.3 | open |
| G2 | No deep link `?project=` in the editor | Home cannot open a specific project; refreshes fall back to "most recent" | W1.2 | **in progress** |
| G3 | No conflict resolution UI on save | Concurrent edits can overwrite | W2.2 | open |
| G4 | No offline draft | A network blip loses the last edit burst | W2.3 | open |
| G5 | No unsaved-changes guard | Navigation can drop a pending write | W2.4 | open |
| G6 | No marquee multi-select / multi-drag / copy-paste | Slower bulk arrangement work | W3 | open |
| G7 | No snap guideline while dragging | Users cannot tell where a clip will land | W3 | open |
| G8 | No drag threshold | 2 px pointer jitter repositions a clip | W3 | open |
| G9 | No clip focus management on delete | Keyboard users lose their place | W3 | open |
| G10 | No master loudness/true-peak readout | Cannot verify a master professionally | W4.4 | open |
| G11 | No mastering presets / export normalisation | Export loudness varies | W4.1 | open |
| G12 | Library lacks stems/projects/upload tabs | Sources scattered across surfaces | W3 | open (needs API for stems listing) |
| G13 | No Studio test suite | Regressions found by hand | W5 | open |
| G14 | No axe/Lighthouse pass on Studio routes | Unknown a11y debt | W5.5 | open |
| G15 | 6.9k-line editor component | Slow review, hard extraction | after W3 | open |
| G16 | No generation history view | Users cannot retrace how a clip was made | W3 | open |
| G17 | No playback speed control | Cannot audition at half speed | W3 | open (PLY-020) |
| G18 | No first-run onboarding in the DAW | New users face a dense UI | W3 | open |
| G19 | Long-project rendering not virtualised | Perf cliff | W3 | open |
| G20 | No touch-target sizing | Unusable on tablets | W3 | open |

## 3. Deliberate non-parity

| Item | Why |
|---|---|
| Branding, logo, copy, artwork | Must be original (mission rule, D-004) |
| Provider-specific model names and marketing labels | We surface our own models and let the provider adapter map them |
| Reference private API usage | Forbidden as a product dependency (D-002) |
| Reproducing the reference's exact pixel metrics | We match interaction quality and density, not pixels; our tokens are ours |
| "Projects" tab in the library drawer | Needs a projects API listing distinct from the studio list; parked until the home ships and the need is proven |

## 4. What we have that the reference does not (or does not obviously expose)

These are wins to protect, not to remove:

- Track groups A–D with group mix and collapse.
- Full clip automation for volume and pan.
- Alternates/takes per clip.
- Project JSON import/export with lossless round trip.
- Per-track and multitrack ZIP export from the browser.
- Shared-project long-poll updates and presence.
- Studio AI command bar (our own).

## 5. Verification debt

Nothing in this repository currently proves the Studio works end to end. The matrix
marks most features `IMPLEMENTED`, not `VERIFIED`, on purpose. Closing that debt is
M11/M12 and is the difference between "looks complete" and "is complete".
