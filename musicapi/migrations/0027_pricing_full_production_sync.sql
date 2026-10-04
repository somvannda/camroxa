-- 0027_pricing_full_production_sync — align every seeded operation price with
-- production.
--
-- The production pricing table (admin.musicapi.camxora.com/admin/pricing) is the
-- source of truth. Each endpoint is set to its production credit cost and any
-- missing endpoint is inserted. Idempotent: re-running is a no-op.

UPDATE pricing p
SET credit_cost = v.cost
FROM (VALUES
  ('add_instrumental', 10),
  ('add_vocals', 10),
  ('boost_style', 0),
  ('cover', 10),
  ('cover_detail', 0),
  ('cover_image', 0),
  ('extend', 10),
  ('lyrics', 0),
  ('lyrics_detail', 0),
  ('mashup', 10),
  ('midi_detail', 0),
  ('midi_generate', 3),
  ('mp3_download', 0),
  ('mp4_detail', 0),
  ('mp4_generate', 2),
  ('music', 10),
  ('persona', 0),
  ('recovery_audio', 10),
  ('recovery_detail', 0),
  ('remaster', 10),
  ('replace_section', 9),
  ('sounds', 3),
  ('stems', 8),
  ('stems_advanced', 12),
  ('stems_detail', 0),
  ('stems_split', 20),
  ('subtitle_detail', 0),
  ('timestamped_lyrics_detail', 0),
  ('upload_cover', 10),
  ('upload_extend', 10),
  ('upload_init', 1),
  ('upload_register', 1),
  ('video_detail', 0),
  ('voice_apply', 10),
  ('voice_extend', 10),
  ('voice_generate', 10),
  ('voice_phrase', 1),
  ('voice_record', 1),
  ('voice_validate', 1),
  ('wav', 0),
  ('wav_detail', 0),
  ('wav_download', 0)
) AS v(endpoint, cost)
WHERE p.endpoint = v.endpoint
  AND p.model IS NULL
  AND p.credit_cost <> v.cost;

INSERT INTO pricing (endpoint, model, credit_cost)
SELECT v.endpoint, NULL, v.cost
FROM (VALUES
  ('add_instrumental', 10),
  ('add_vocals', 10),
  ('boost_style', 0),
  ('cover', 10),
  ('cover_detail', 0),
  ('cover_image', 0),
  ('extend', 10),
  ('lyrics', 0),
  ('lyrics_detail', 0),
  ('mashup', 10),
  ('midi_detail', 0),
  ('midi_generate', 3),
  ('mp3_download', 0),
  ('mp4_detail', 0),
  ('mp4_generate', 2),
  ('music', 10),
  ('persona', 0),
  ('recovery_audio', 10),
  ('recovery_detail', 0),
  ('remaster', 10),
  ('replace_section', 9),
  ('sounds', 3),
  ('stems', 8),
  ('stems_advanced', 12),
  ('stems_detail', 0),
  ('stems_split', 20),
  ('subtitle_detail', 0),
  ('timestamped_lyrics_detail', 0),
  ('upload_cover', 10),
  ('upload_extend', 10),
  ('upload_init', 1),
  ('upload_register', 1),
  ('video_detail', 0),
  ('voice_apply', 10),
  ('voice_extend', 10),
  ('voice_generate', 10),
  ('voice_phrase', 1),
  ('voice_record', 1),
  ('voice_validate', 1),
  ('wav', 0),
  ('wav_detail', 0),
  ('wav_download', 0)
) AS v(endpoint, cost)
WHERE NOT EXISTS (
  SELECT 1 FROM pricing p WHERE p.endpoint = v.endpoint AND p.model IS NULL
);
