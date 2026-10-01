-- 0017_wav_free — WAV is download-only, so the conversion endpoints are free.
--
-- `POST /v1/music/wav`, `GET /v1/music/wav/:id` (and the `/me` + `/api/v1`
-- aliases) only resolve a signed URL. The bytes are delivered by
-- `GET /me/download?format=wav`, which is where the `wav_download` charge
-- applies. The routes stay for sunoapi parity, but at 0 credits the natural
-- two-step flow can no longer double-charge.
--
-- WAV is never streamed: playback reads the clip's mp3 `audio_url` and falls
-- back to `/me/download?format=mp3`.
--
-- `pricing` has no unique key to conflict on, so this is an UPDATE rather than
-- an upsert; a missing row still resolves to 0 through `DEFAULT_COSTS`.

UPDATE pricing
SET credit_cost = 0
WHERE endpoint IN ('wav', 'wav_detail') AND model IS NULL AND credit_cost <> 0;
