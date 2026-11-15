# Web Create: a refused lyrics prompt now says why, and retries without the pool line

**Date:** 2026-11-15
**Surface:** `platform_api` (web music), `musicapi` (lyrics record-info)
**Branch:** `fix/lyrics-rejection-message`

## Summary

The first live 5-song Simple-mode batch after the 524 fix produced one song and
four failures that all said:

> This song could not be written. Credits were refunded.

The credits were refunded correctly, but the reason was lost twice:

1. **`musicapi` reported success for a rejected prompt.** Suno answers a refused
   lyrics prompt with a *finished* task and no text:

   ```json
   {"text": "", "title": "", "status": "error",
    "error_message": "Your prompt contains producer tag lowlight - we don't
                      reference specific artists on Suno, please change your
                      prompt and try again."}
   ```

   `processLyricsSubmit()` returned that object, so `runResultJobWithRetry()`
   marked the job `complete`, and `lyricsRecordInfo()` answered `SUCCESS` with
   `response: null`. `platform_api` could only report "lyrics returned no
   completed variants".

2. **`platform_api` replaced the reason with a generic sentence.** The failure
   path hardcoded "This song could not be written. Credits were refunded."

The offending phrase came from the **content pool**, not the listener: four of
the five prompts opened with the same pooled line, `the low-light ocean`, and
Suno's artist filter read `low-light` as the producer tag `lowlight`.

## Product impact

- A refused prompt now says what to change, e.g. *"Suno refused this prompt
  because it reads like an artist or producer reference. Change the description
  and try again. Credits were refunded."* Any other provider reason is shown
  verbatim (trimmed).
- A rejected **pool opening line** no longer costs the listener a song: the seed
  is released and the lyrics are written once more without it. The batch that
  produced 1 of 5 songs would now produce all five.
- Refund behaviour is unchanged: one refund per failed song, and a retried job
  still cannot deliver a refunded song.

## Technical impact

- `musicapi/src/server.ts`
  - `processLyricsSubmit()` throws when the task finishes without text, carrying
    Suno's `error_message`. The job therefore keeps a real `error` (visible in
    logs, `jobs.error` and the admin views) and the retry policy decides: a
    content rejection fails fast (no retryable token in the message), a missing
    text/timed-out task keeps "timed out" and is retried on another account.
  - `lyricsRecordInfo()` is now truthful for stored jobs too: `complete` with no
    text maps to `GENERATE_LYRICS_FAILED` with the provider message, instead of
    `SUCCESS` with an empty `response`. `hasLyrics` also requires non-empty text
    (`typeof "" === "string"` was the original hole).
- `platform_api/services/web_music_service.py`
  - New `lyrics_failure_user_message()` strips the `Suno failed (STATUS):`
    frame, recognises the artist/producer refusal, and falls back to the generic
    sentence only when there is nothing useful to say.
  - `write_queued_lyrics()` stores that message on the failed row.
  - `_write_simple_song()` retries once **without** the forced pool opening when
    the lyrics call raises `ExternalServiceError`, releasing the seed item.
- Tests: `platform_api/tests/test_web_music_diversity.py` covers the message
  mapping, the retry-without-opening path, and that the refusal reason lands in
  `suno_tasks.error_message`.

## Migration / deploy

No schema change. Two deploys:

```
python scripts/deploy/deploy_musicapi_production.py --yes --api-only
python scripts/deploy/sync_platform_api_production.py
```

## Tests

- `platform_api`: 3462 passed (2 deselected: the Windows-only media path cases).
- `musicapi`: `npx tsc --noEmit` clean.

## Follow-ups

- The opening pool served the *same* two-line opening to four songs of one batch,
  which also erases the per-song diversity the planner adds. `claim_pool_item`
  needs to avoid repeating a recent opening within a batch.
- `suno_status_messages.classify_suno_failure_type()` already knows
  `"producer tag"`; the lyrics path could use it to pre-check a prompt before
  charging.
