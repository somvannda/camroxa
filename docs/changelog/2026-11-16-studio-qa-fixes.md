# Studio QA fixes: a data-loss guard, a false conflict, and invisible waveforms

**Date:** 2026-11-16
**Surface:** `camxora.com/components/studio`, `camxora.com/lib`
**Found by:** the three-agent QA pass — reports in `docs/studio/reports/2026-11-16-agent-*.md`

## Summary

The QA team tested the Studio the way a user would: A drove every feature in a browser,
B compared all 73 captured Suno screens with ours, C re-derived every claim from the code.
Three real product defects came out of it and are fixed here.

## D1 — editing before the project loads deleted every clip

`writeProjectData` persisted `{ ...currentData(), tracks }`. Before the first load resolves
`currentData()` is `{}`, the write sent no `expected_updated_at`, and the server replaces
`data` wholesale (`COALESCE($7::jsonb, data)`). Pressing `a` (add track) while “Loading
project…” showed therefore erased the arrangement permanently.

- **Fix:** `writeProjectData` refuses while there is no document and shows “This project is
  still loading. Try again in a moment.”
- **Test:** `studio-persistence.spec.ts` › *editing while the project is still loading cannot
  erase it* — holds the GET, presses the shortcut, asserts the stored lanes are intact.
  Fails on the old code, passes now.

## D2 — renaming made the next edit a phantom conflict

The rename PATCH bumps `updated_at`, but `onRenamed` carried only the title, so the cached
version stayed stale and the next save 409'd with “changed in another tab”.

- **Fix:** `onRenamed(title, updated_at)`; the shell updates `projectVersionRef` synchronously
  and the project state's `updated_at`. Both rename paths (menu and share naming gate) pass it.
- **Tests:** `studio-project-menu.spec.ts` › *renaming then editing does not raise a false
  conflict* (fails on the old code), plus unit assertions that the version is forwarded.

## C1 — timeline waveforms could stay invisible

`computePeaks` swallowed every fetch/decode failure and `Waveform` drew only on success, so a
cross-origin audio host without CORS produced flat colour blocks with no hint why. Peaks were
also cached *including* failures, so one transient error blanked the clip for the session.

- **Fix:** `computePeaks` retries once and evicts the cache entry on failure; `Waveform`
  always paints — peaks when ready, a dim baseline when not — and records the state in
  `data-waveform="pending|ready|fallback"`.
- **Tests:** `tests/studio-waveform.test.tsx` (ready / fallback / no-url) and
  `tests/e2e/studio-waveform.spec.ts` (same-origin audio reaches `ready`; a 500 becomes
  `fallback`).

## What is *not* fixed here

The parity and cosmetic rows in the consolidated ledger (shortcuts panel, onboarding tiles,
transport geometry, share copy/permissions, menu ordering, clip-info rail, key/BPM tags).
They are documented and ranked in `docs/studio/reports/2026-11-16-agent-c-consolidated.md`
and need their own branch.

> **Correction (2026-11-17).** The blank clip bodies that supported C1 in the captures were
> partly a **fixture bug**: the capture script requested `/demo-loop.wav` while the asset is
> `/seed/demo-loop.wav`, so 31 scenarios never decoded audio. The C1 fix stands on its own
> terms — a failed fetch or a cross-origin decode without CORS still produced an invisible
> canvas and a cached failure — but the capture evidence alone did not prove it. W10 fixed
> the fixture and re-shot the frames; the renderer now reports `data-waveform` state.

## Verification

Vitest **376** · Playwright **182 passed / 2 skipped** on the lean mirror · typecheck +
`check:ui` clean · `check:clone` satisfied (73/73 screens, 70/70 strings).

## Follow-up this pass found but did not fix

`refresh_studio_project` re-arms `enqueue` whenever a project has no Suno link. The enqueue
timeout is 90 s, so a mirror that cannot link (our sandbox account 404s) turns every editor
poll into a 40 s provider call — one full suite run saw `/refresh` at 41–43 s. With a healthy
mirror the project links once and this never repeats; with a failing one it is a load storm.
The fix is a backoff/attempt stamp before re-arming, not a longer timeout.
