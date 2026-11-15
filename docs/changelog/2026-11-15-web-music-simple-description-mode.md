# Web Create: Simple mode hands the description to Suno and just queues

**Date:** 2026-11-15
**Surface:** `platform_api` (web music), `music_web`
**Commit:** `d5b032fe`
**Branch:** `feat/web-simple-description-mode` (merged, deleted)

## Summary

Simple mode called Suno's lyrics API first and then submitted the result in
custom mode. That second call bought a title and lyrics, and everything built on
top of it existed only to police them:

- a 45s lyrics wait, and before that a 120s one that caused HTTP 524 on batches
- refund-on-lyrics-failure, retry-without-the-pool-opening
- an admin blocklist that refused words **we** injected: the learned term
  `lowlight` matched the pool opening "the low-light ocean", so 4 of 5 songs of a
  real batch died with "Remove Suno-blocked wording before creating: low-light"
- placeholder titles in the queue, because the card now exists before the song
  does

The listener's description is the only input Suno needs. One call does it.

## Product impact

- Simple mode: describe → **Suno writes the title and the lyrics** and returns
  both versions. Our side queues, files and shows.
- No lyrics step means no lyrics timeout, no lyrics refunds, no "blocked wording"
  for text we generated, and ~2 provider credits cheaper per song.
- Cards read "Writing song…" until Suno returns the name; the real title, lyrics
  and lyric sheet then come from the clip itself.
- Batch variety still comes from the planned angle (theme + section order + an
  optional listener title), now folded into the description instead of being
  forced into lyric lines.
- Advanced mode, cover/extend/sample and sounds are unchanged: they still submit
  the exact text in custom mode.

## Technical impact

- `clients/suno_client.py`: `submit_task(description=...)` sends
  `customMode: false` + `gpt_description_prompt` and skips the custom-mode
  title/lyrics validation. `SunoGeneratePollResult` and the clip parsers now carry
  `title_ok`, `title_alt` and `lyrics` (`metadata.title` / `metadata.prompt`).
- `ports/generation_port.py`, `services/generation_service.py`: `SunoRequest`
  carries the description through `_call_suno`.
- `services/web_music_service.py`: `build_web_simple_description()` composes the
  one description; `fulfill_queued_generate()` submits in description mode when
  the row has no lyrics and a saved brief; `_refresh_pending_from_suno()` persists
  the polled title/lyrics.
- `routers/callbacks.py`: the completion callback persists the clip title/lyrics on
  `web_music` rows, only where they are still empty.
- `worker.py`: no longer calls `write_queued_lyrics()`.
- `music_web`: the queued-row label is "Writing song…".

## Migration / deploy

No schema change. `musicapi`'s `gpt_description_prompt` compat route (`26c28f40`)
is a prerequisite and was deployed earlier (`0b2b000d`).

```
python scripts/deploy/sync_platform_api_production.py
python scripts/deploy/sync_music_web_production.py
```

## Tests

- New `platform_api/tests/test_web_simple_description_mode.py` (6): description
  builder, poll title/lyrics parsing, persistence on completion, queued submit
  passes a description rather than lyrics.
- Full suite: 3479 passed (2 deselected, Windows-only media paths).
- `music_web`: `npm run build` clean.

## Follow-ups

- `write_queued_lyrics()`, `_write_simple_song()` and their tests are now dead for
  Simple mode; delete them together with the `lyrics_brief` column once a batch
  confirms the description flow.
- Verify with a real 5-song batch: distinct titles, genre still follows `style`,
  lyrics present on the library card and the lyric sheet.
