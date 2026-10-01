-- 0013_download_pricing — make audio delivery via `GET /me/download` editable at
-- /admin/pricing, one row per format.
--
--   mp3_download — inline playback and MP3 downloads. Free by default: the player
--                  streams straight from the CDN, and MP3 is the lossy format.
--   wav_download — lossless WAV downloads. Charged a credit.
--
-- These are kept separate from `wav`, which prices the async WAV *conversion*
-- API (`POST /v1/music/wav`, `POST /api/v1/generate/convert-wav`).
--
-- `pricing` has no unique key to conflict on, so a plain ON CONFLICT DO NOTHING
-- would insert duplicates on every run.
INSERT INTO pricing (endpoint, model, credit_cost)
SELECT v.endpoint, NULL, v.credit_cost
FROM (VALUES
  ('mp3_download', 0),
  ('wav_download', 1)
) AS v(endpoint, credit_cost)
WHERE NOT EXISTS (
  SELECT 1 FROM pricing p WHERE p.endpoint = v.endpoint AND p.model IS NULL
);
