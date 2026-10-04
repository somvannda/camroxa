-- 0026_pricing_production_alignment — make every environment charge the same
-- prices as production, and un-invert the top of the credit-pack ladder.
--
-- 1. Best-value $100 rung: 33,000 credits was 330 credits/$1, *less* than the
--    $60 pack (333.33/$1), so the biggest pack was not the best rate. Bump it
--    to 35,000 (350/$1) so the ladder is monotonic and "Best value" is honest.
--    The row is updated in place, so historical `payment_transactions.pack_id`
--    links survive.
-- 2. Per-endpoint credit costs: align with the live production/sandbox snapshot
--    so a database built from scratch, the sandbox and production all charge
--    the same. Idempotent — rows are updated in place (ids preserved), missing
--    endpoints inserted, matching rows untouched. A no-op on environments
--    already at parity.

-- ---- 1. Pack rung ---------------------------------------------------------
UPDATE credit_packs
SET amount = 35000
WHERE currency = 'USD' AND amount = 33000;

-- ---- 2. Endpoint costs (production snapshot) ------------------------------
CREATE TEMP TABLE _pricing_snapshot (endpoint TEXT PRIMARY KEY, cost INTEGER NOT NULL) ON COMMIT DROP;

INSERT INTO _pricing_snapshot (endpoint, cost) VALUES
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
  ('wav_download', 0);

UPDATE pricing p
SET credit_cost = s.cost
FROM _pricing_snapshot s
WHERE p.endpoint = s.endpoint
  AND p.model IS NULL
  AND p.credit_cost <> s.cost;

INSERT INTO pricing (endpoint, model, credit_cost)
SELECT s.endpoint, NULL, s.cost
FROM _pricing_snapshot s
WHERE NOT EXISTS (
  SELECT 1 FROM pricing p
  WHERE p.endpoint = s.endpoint AND p.model IS NULL
);

DROP TABLE _pricing_snapshot;
