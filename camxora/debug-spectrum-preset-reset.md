[OPEN] Debug Session: spectrum-preset-reset

## Summary
- Symptom: While editing the spectrum with `Straight Bars`, the UI resets back to the original preset `Liquid Mass`.
- Expected: Unsaved local edits must persist during the current app session and never reload/reset unless the app is closed or the user explicitly loads another template/preset.
- Save rule expected by Boss: once Save is hit, the current local state should become the persisted state and override the prior saved settings.

## Hypotheses (Falsifiable)
- A: A sync effect in `VideoWorkspacePage.tsx` rehydrates `templateDraft` from `workspace.template` after query refresh, overwriting unsaved local edits.
- B: Buffered patch/save calls complete out of order and a stale response reintroduces `Liquid Mass`.
- C: More than one preset source of truth still exists (e.g. `templateDraft.style` vs another derived state), causing a revert.
- D: A refetch triggered by save or unrelated controls rebuilds the draft from older backend/template data.
- E: Layer synchronization logic mutates the draft or style key when spectrum layers change, indirectly resetting the preset family.

## Instrumentation Plan
- Log every local style transition, every workspace/template style hydration, and every outgoing template patch touching spectrum fields.
- Compare timestamps to determine whether local edits are overwritten by workspace/query refresh or by patch/save race.

## Status
- Evidence collected:
  - Code path confirmed in `VideoWorkspacePage.tsx`:
    - buffered spectrum edits call `patchTemplate(... deferRefresh: true)`
    - successful buffered patches queue `invalidateQueries(['video-workspace'])`
    - the workspace hydration effect rebuilt `templateDraft` from `data.template` on every refresh, regardless of whether the current template id changed
  - Regression test added in `VideoWorkspacePage.test.tsx` proving same-template refresh must preserve local preset selection.

## Root Cause
- Same-template workspace refetches were overwriting the in-session local spectrum draft because the hydration effect always rebuilt `templateDraft` from backend workspace data.

## Fix
- Hydrate `templateDraft` only on first load or when `templateId` changes.
- Preserve the in-session local draft for the current template across query refreshes.

## Verification
- `npm run check`
- `npx vitest run src/renderer/src/features/video/VideoWorkspacePage.test.tsx`

## Status
- Awaiting Boss confirmation in the real app before cleanup.
