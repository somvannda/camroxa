# Studio: "Sample this song" is wired end to end

**Date:** 2026-11-14
**Surfaces:** camxora.com (Create/song menu), platform_api, musicapi
**Status:** implemented locally, gates green, not deployed

## Summary

The song row's **Sample this song** entry was the last disabled generation
control. It now opens Create with the chosen version attached as an audio
reference, and the next generation is submitted through musicapi's existing
agentic audio-reference path (`audio_urls` → `audioIds` → `task: agentic_thinking`).

## Flow

1. Song menu → `/create?sample=<generation>&variant=<ok|alt>`.
2. Create loads the song, pre-fills the advanced form with its style and shows a
   removable **“Sampling <title>”** chip.
3. Submit sends `sample_task_id` + `sample_variant` with the normal generation
   payload.
4. `WebMusicService.generate` checks ownership/readiness, reads the source clip's
   durable `audio_url_{ok|alt}`, and stores it in
   `suno_tasks.reference_audio_urls` (migration `201`).
5. `fulfill_queued_generate` passes the URL as `SunoRequest.audio_urls`; the
   platform client sends `audioUrls`, which musicapi uploads to the generated
   account and composes into the agentic request.

The browser never supplies a provider URL or clip id; only an owned generation
id and variant cross the boundary.

## Tests

| Layer | Result |
|---|---|
| platform service tests | resolve/storing, not-ready refusal, worker forwarding (3) |
| web typecheck / `check:ui` | clean |
| Vitest | **339 passed** |
| Playwright | **162 passed / 2 skipped** (new sample spec; provider mocked) |
| platform pytest | **3402 passed**, 2 pre-existing `test_media_router` failures |
| migration `201` | applied to the local sandbox DB during verification |

## Notes

- The generated sample is a full song referencing the source audio, not a
  shorter clip; Suno's UI wording is the captured label, and the reference
  semantics match musicapi's audio-reference generation.
- Real provider submission is covered by mocked unit/e2e tests; a live run would
  spend credits.
