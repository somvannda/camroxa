# TESTING AND ACCEPTANCE CRITERIA

A feature is complete only when **all seven** conditions hold:

1. UI exists and is reachable.
2. Interaction works (manual run recorded).
3. Backend integration works where required.
4. Data persists where required.
5. Error states are handled.
6. Tests pass.
7. Documentation and the matrix are updated.

Anything less is `IMPLEMENTED`, never `VERIFIED`.

## 1. Test layers

| Layer | Tooling | Scope | Status |
|---|---|---|---|
| L1 unit | none yet — target `node:test` or `vitest` | pure helpers: `snap`, `barBeat`, `encodeWav`, `buildMidiFile`, `parseMidiFile`, `midiVlq`, `normalizeGroups`, `applyGroupMix` | not started |
| L2 component | target React Testing Library | reducer/invariants: undo depth, mute/solo interaction, clip clamp, lane alignment | not started |
| L3 contract | target `node:test` + `undici` mock | every `lib/studio-api.ts` helper: path, method, body, error envelope | not started |
| L4 E2E | target Playwright | journeys W-A…W-H | not started |
| L5 a11y | axe + Lighthouse | `/studio`, `/studio/editor`, `/studio/shared/[token]` | not started |
| L6 manual | this document | evidence for `VERIFIED` | in use |

## 2. Required automated tests (minimum)

### 2.1 L1

| Test | Asserts |
|---|---|
| `snap` | off/bar/beat/1/8/1/16 snap to the expected grid; negative input clamps to 0 |
| `barBeat` | 120 BPM 4/4 → bar 1 beat 1 at t=0; t=2 s → bar 2 beat 1 |
| `encodeWav` | header RIFF/WAVE, channel and sample-rate match input, length = samples×2 |
| `buildMidiFile` / `parseMidiFile` | round trip preserves note count, pitch, start, duration, tempo |
| `midiVlq` | 0, 127, 128, 0x0FFFFFFF encode to documented byte strings |
| `normalizeGroups` | garbage input yields the default four groups |
| `applyGroupMix` | group mute/solo/volume compose in the documented order |

### 2.2 L2

| Test | Asserts |
|---|---|
| undo/redo | N edits → N undos restores the initial arrangement; redo replays; depth is bounded |
| clip clamp | dragging before 0 clamps to 0; trimming below `MIN_CLIP` is refused |
| mute/solo | solo on track A silences B and C; clearing restores prior mutes |
| lane integrity | deleting a track removes its clips and keeps others aligned |
| autosave trigger | mutations schedule exactly one save per debounce window |

### 2.3 L3

One test per helper in `lib/studio-api.ts`:

- correct method and path (including URL encoding of ids/tokens);
- JSON body shape for POST/PATCH;
- multipart shape for uploads;
- `{error:{message}}` and `{detail}` both become the thrown message;
- 204 returns `undefined` without parsing.

### 2.4 L4 (Playwright smoke)

```
studio-home.spec      → /studio renders projects, creates one, opens it
studio-open.spec      → ?project=<id> loads that project, not the most recent
studio-arrange.spec   → add track, drop clip, move, trim, split, undo, redo
studio-mix.spec       → volume/pan/mute/solo change audio graph state and persist
studio-export.spec    → WAV export downloads with a plausible size
studio-share.spec     → create link, open shared page, comment, revoke
```

## 3. Manual acceptance (per journey)

Record in `PROJECT_PROGRESS.md`: date, build (commit), environment, result, defects.

| Journey | Minimum bar |
|---|---|
| W-A first project | create → edit → reload → nothing lost |
| W-B song into arrangement | clip lands, splits/duplicates survive reload |
| W-C mix | every mix change audible and reversible |
| W-D export | files valid; JSON round trip lossless |
| W-E paid ops | cost shown, charged once, failure refunds |
| W-F collaboration | shared edit, comment, revoke all behave |
| W-G failure paths | no silent failures, no data loss |
| W-H advanced edit | MIDI round trip, reverse/fade/speed correct |

## 4. Non-functional criteria

| Criterion | Target | How measured |
|---|---|---|
| Load time (editor, warm) | < 2.5 s TTI | Lighthouse / trace |
| Drag frame time | < 16 ms p95 | performance trace during drag |
| 200 clips | 60 fps scroll | synthetic project benchmark |
| Autosave round trip | < 400 ms p95 | network timing |
| Export 3 min stereo | < 15 s | stopwatch in E2E |
| Accessibility | no serious axe violations on Studio routes | axe run |
| Contrast | ≥ 4.5:1 body text | token audit |
| Cross-browser | Chromium + Firefox + WebKit pass smoke | Playwright matrix |
| Keyboard-only | every journey completable without a pointer | manual script |

## 5. Definition of done (per feature row)

```
[ ] UI reachable and labelled
[ ] Interaction spec row exists
[ ] Success path recorded (date + commit)
[ ] Failure path recorded
[ ] Persistence verified after reload (if it writes data)
[ ] Automated test exists (L1–L4 as applicable)
[ ] Matrix status = VERIFIED with evidence link
```

## 6. Regression rule

Any bug fixed gets a test at the lowest layer that can reproduce it. If a bug cannot
be tested, that is a design smell — record it in `PROJECT_BLOCKERS.md`.
