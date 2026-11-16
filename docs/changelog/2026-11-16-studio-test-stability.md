# Studio e2e: prove the environment, then stop calling its noise a bug

**Date:** 2026-11-16
**Surface:** `camxora.com/tests/e2e`, `docs/studio/SESSION_HANDOFF.md`
**Commits:** `89c75be2` · `ba84f2e0` · `ac2c0812` · `f9875e54` · `86a3b639` · `40c5133d`
**Branch:** `chore/session-resume` (merged)

## Summary

The suite kept going red for reasons that were **not** in the product. Each failure was
traced to a measurement before it was changed:

| Symptom | What was actually happening |
|---|---|
| `Stems` matched 19 buttons | the shared sandbox corpus now holds songs titled “Stems live check …” |
| 0 library rows | the corpus can be emptied by another session between runs |
| Suno sync dialog never settles | a live mirror’s first push creates the remote project: **18 s** via API, **32 s** in the browser |
| Recently Deleted has no row | the deleted-list query answered **200 in 10.5 s**, one second over the expect window |
| bounce fails | the offline render plus upload took **20 s**; the 8 s download wait expired first |
| warp mode not saved | a queued save exceeded the default 10 s poll |

No product behaviour changed in this pass.

## Product impact

None. The specifications still exercise the real API and UI where the data exists:

- name-based locators are scoped to the element that owns them (`toolbar "Song filters"`,
  group `Library filters`) instead of matching every song whose title starts with the word;
- two library specs that read real generation rows **skip with a reason** when the corpus is
  empty, and run normally when it is not;
- the Send-to-Suno dialog is a UI test with a stubbed answer; the live push is verified
  separately and is not a suitable thing to assert inside a 120 s test;
- the bounce spec races its two legitimate outcomes (placed track vs downloaded WAV) instead
  of assuming one lands inside a fixed window.

## Technical impact

- `studio-library.spec.ts`: toolbar-scoped controls, `hasCorpus()` guard.
- `studio-stems.spec.ts`: tile resolved inside `Library filters`.
- `studio-project-menu.spec.ts`: `POST /sync` stubbed; sentence asserted.
- `studio-bounce.spec.ts`: `Promise.race` over download vs placed track, 90 s bound.
- `studio-warp.spec.ts`: 30 s polls on the saved document.
- `studio-soft-delete.spec.ts`, `studio-pixel.spec.ts`, `library-*.spec.ts`: 30 s windows on
  lists that have measured over 10 s.
- `SESSION_HANDOFF.md`: the 2026-11-16 rebuild note and the working stack recipe (env files
  from the canonical checkout, Studio token, moto storage, worker).

Every window stays bounded, so a genuine hang still fails.

## Gate hardening (same day)

`check:clone` accepted two weak signals, so rule 1 and rule 3 were softer than they claimed:

- a named spec that **exists but is entirely skipped** counted as screen coverage;
- functional strings were matched against `.md` files as well, so a document could satisfy a
  string that the UI no longer ships.

Both now fail closed:

- a named spec must contain at least one runnable `test(`/`it(` declaration (`test.skip(`
  and `it.skip(` do not count; in-body gates still do);
- rule 3 matches `.ts`/`.tsx`/`.css` source only.

Proven in both directions with a disposable probe: an entirely-skipped spec and a doc-only
string each failed the gate with the exact message, and the real gate stays green.

## Verification

- Playwright on the storage-backed stack: **178 passed / 2 skipped** (8.5 min, 2 workers).
- Storage paths: record→take and bounce→bucket, **3 objects** in moto; `/sync` created a real
  Suno project.
- typecheck · `check:ui` · `check:clone` (73/73 screens, 70/70 strings) · Vitest **373** ·
  musicapi unit **198** · platform pytest **3479**.

## Notes

The local stack’s node/python processes do not survive between long tool sessions on this
machine. The reliable pattern is to start moto, the API, musicapi and web **and** run the
suite in the same shell lifetime; `scripts/dev/studio-stack.ps1 -Status` is the quick check.
