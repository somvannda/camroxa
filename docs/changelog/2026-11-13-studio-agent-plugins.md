# Designed plugins now run on Suno's authoring agent

**Date:** 2026-11-13
**Branch:** `feat/studio-agent-plugins` (stacked on `fix/studio-pull-chain-merge`)
**Surfaces:** camxora.com (Studio editor), platform_api, musicapi, docs
**Status:** implemented, gates green, not merged or deployed

## Summary

The last open parity item is closed. Designed plugins no longer come from a
deterministic local heuristic; "Build it" asks Suno's authoring agent for a real
DSP plugin, saves the result into the pinned account's plugin library, and mirrors
it in the project's signal chain with `catalogPluginId` + `pluginVersionId`.

This was a product decision (option 1 of three) recorded in
`docs/studio/PARITY_REMOVAL_LIST.md`; the live contract, probe evidence and
payloads are in `docs/studio/SUNO_STUDIO_AGENT_PLUGINS.md`.

## Product impact

- Opening Create new plugin keeps the captured flow: restate, ask, then build.
  The restate now says the agent spends credits.
- Build shows the agent's own progress ("Rendering test audio to verify the
  sound"), then a draggable card; it is never inserted automatically.
- A built plugin survives a save/pull round trip, and a project opened on another
  device hydrates the controls from the Suno library.
- Percent controls authored by Suno keep 0–1 values and read as 0–100 % in the
  knob, so what mirrors is what the user sees.

## Technical impact

- `musicapi/src/client.ts`: `authorPlugin`, `getPluginAuthoringJob`,
  `createPlugin`, `savePluginVersion`, `getPlugin`.
- `musicapi/src/sunoStudio.ts`: `authorPlugin`, `pluginAuthoringJob` (idempotent
  claim, retry reuses the created library plugin, stale claims released),
  `customPluginSnapshots` for pulls.
- Migration `0045_studio_plugin_authoring.sql`: job ledger, applied locally.
- Internal routes `POST/GET /internal/studio/projects/:id/plugins/author…`.
- platform_api proxies the two web calls after ownership checks.
- `musicapi/src/studioStateCodec.ts`: custom-entry mapping in both directions,
  `sunoPluginToLocalCustom`, and chain re-keying to local track ids.
- Web: `lib/studio-designer.ts` converts descriptors; the shell polls the job;
  `ParamKnob` renders 0–1 percent controls as percentages.

## Behaviour fixed along the way

- A pulled chain was stored under Suno's track id (unreadable by the editor) and
  a pull replaced the whole chain. Chains now merge per entry against the local
  track id: Suno wins for representable effects (so deletes propagate), an entry
  with no Suno ids is kept and reported, and dropped tracks leave no orphan
  chains.

## Tests

| Layer | Result |
|---|---|
| musicapi typecheck | clean |
| musicapi (`tsx --test`) | 198 passed |
| platform_api pytest | 3386 passed, 2 pre-existing `test_media_router` failures (missing local uploads path, untouched code) |
| Vitest | 334 passed |
| `check:ui` | clean |
| Playwright | **156 passed / 2 skipped** (158 tests) |

The designer e2e mocks the two proxied authoring calls, so the full UI flow runs
without spending credits; musicapi tests cover the codec, merge and coverage
registry.

## Follow-ups

- The local audio engine approximates the authored DSP by family; executing
  Suno's plugin code is out of scope.
- Authoring spends Suno credits and has no local pricing row yet, so the sync
  chip does not show a cost.
- Merge to `main` and deploy remain ship decisions (not done here).
