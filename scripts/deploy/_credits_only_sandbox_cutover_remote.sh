#!/bin/bash
set -euo pipefail
APPLY="${APPLY:-0}"
FLAG_ON="${FLAG_ON:-0}"
echo "HOST=$(hostname) APPLY=$APPLY FLAG_ON=$FLAG_ON"
if ip -4 addr | grep -q '82.197.71.248'; then
  echo "Refusing production host"
  exit 1
fi

echo "=== plans before ==="
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT name, price_cents, profile_allowance, billing_cycle_days,
       monthly_song_limit, monthly_credits, is_active, is_public,
       plan_kind, plan_type, music_credits, video_credits
FROM plans
ORDER BY plan_kind, price_cents, name;
"

sudo -u postgres psql -d camxora_platform -v ON_ERROR_STOP=1 <<'SQL'
UPDATE plans
SET
  monthly_credits = COALESCE(monthly_song_limit, 0) * 10,
  daily_credits = 0,
  is_public = false,
  lyric_credits = 5,
  title_credits = 3,
  album_credits = 3,
  music_credits = 10,
  style_credits = 2,
  image_credits = 5,
  video_credits = 0,
  merge_credits = 0,
  updated_at = NOW()
WHERE COALESCE(plan_kind, 'subscription') = 'subscription'
  AND COALESCE(plan_type, 'desktop_pro') = 'desktop_pro'
  AND price_cents > 0
  AND monthly_song_limit IS NOT NULL;

-- Hidden 2-channel monthly analog: leftover still uses song_limit; grant is the spec 3,000.
UPDATE plans
SET monthly_credits = 3000, updated_at = NOW()
WHERE name = 'Monthly · 2-channel'
  AND profile_allowance = 2
  AND billing_cycle_days = 30;
SQL

echo "=== desktop subscription plans after ==="
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT name, price_cents, profile_allowance, billing_cycle_days,
       monthly_song_limit, monthly_credits, is_active, is_public,
       music_credits, lyric_credits, video_credits, merge_credits
FROM plans
WHERE COALESCE(plan_kind, 'subscription') = 'subscription'
  AND COALESCE(plan_type, 'desktop_pro') = 'desktop_pro'
  AND price_cents > 0
ORDER BY profile_allowance, billing_cycle_days, name;
"

echo "=== credits snapshot before leftover apply ==="
python3 /tmp/credits_cutover_snapshot.py dump /tmp/credits-snapshot-before.csv

sudo -u camxora bash -lc "cd /opt/camxora/repo && source platform_api/.venv/bin/activate && export PYTHONPATH=/opt/camxora/repo && APPLY=$APPLY FLAG_ON=$FLAG_ON python /tmp/credits_only_sandbox_cutover.py"

echo "=== credits snapshot after leftover apply ==="
python3 /tmp/credits_cutover_snapshot.py dump /tmp/credits-snapshot-after.csv
python3 /tmp/credits_cutover_snapshot.py diff /tmp/credits-snapshot-before.csv /tmp/credits-snapshot-after.csv
echo SANDBOX_CUTOVER_PHASE_DONE
