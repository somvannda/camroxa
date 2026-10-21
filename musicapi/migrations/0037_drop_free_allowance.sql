-- 0037_drop_free_allowance — remove the musicapi monthly V6-Mini allowance.
--
-- The 50-credit monthly grant belongs to the consumer app at music.camxora.com
-- (platform_api / music_web), not to the musicapi API. musicapi is back to
-- paid-only credits: a user must buy a pack to generate, and V6-Mini is priced
-- by the normal `pricing` table.
--
-- Migrations 0034-0036 are kept in the repo for history because they were
-- applied to production; this file reverses their schema.

DROP TABLE IF EXISTS monthly_allowances;

ALTER TABLE jobs DROP COLUMN IF EXISTS allowance_credits;
ALTER TABLE jobs DROP COLUMN IF EXISTS allowance_period;

ALTER TABLE usage_logs DROP COLUMN IF EXISTS allowance_credits;

-- The model-scoped V6-Mini row was added by 0034. The endpoint-wide
-- `music = 10` row applies again, so remove the model override.
DELETE FROM pricing WHERE endpoint = 'music' AND model = 'chirp-goose';
