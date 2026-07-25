# Music plan image cost is per batch, not per song

**Date:** 2026-07-25  
**Status:** implemented (desktop restart required)

## Summary

The Music automation plan showed Image totals like `640 credits (16 image jobs per song)` for `1 day × 4 pairs × 10 songs`. Album images are one BG + one TH per Primary/Secondary **per batch**, so 4 batches × 4 jobs = **16 jobs total**, not 16 × 40 songs. The estimate now matches server billing.

## Product impact

- **Before:** Image line could be ~40× too high; Batch total looked unaffordable. Long multi-line plan sat above Generate.
- **After:** Image total = unit × album jobs across planned batches. Compact plan summary sits in a framed panel **under** Generate (e.g. `4 batches · 40 songs` / Draft · Suno · Image / Total). Backend billing was already correct; only the desktop estimate was wrong.

## Technical impact

- `get_music_plan_cost_breakdown` / `get_batch_generate_total_cost` in `music_costs.py` (per-batch album jobs).
- Plan copy in `music_view.py`; credit formatting avoids `7.199999…`.
- `AutomationCard`: plan text moved below Generate into `QFrame#music_plan_summary` (`#0f1923`).
- Theme QSS for `#music_plan_summary` / `#music_plan_summary_text`.
- Platform `_calculate_batch_cost`: image = `(ok + alt profile jobs) × image_price` once per batch — **not** × song_count (unchanged; correct).

## Files touched

- `camxora_python/shared/lib/music_costs.py`
- `camxora_python/features/music/views/music_view.py`
- `camxora_python/features/music/widgets/automation_card.py`
- `camxora_python/shared/themes/deep_blue.py`
- `camxora_python/tests/test_music_costs.py`
- `camxora_python/tests/test_automation_card.py`
- `CHANGELOG.md`

## Migration / deploy

- Desktop restart only. No API deploy.

## Tests

- `pytest camxora_python/tests/test_music_costs.py camxora_python/tests/test_automation_card.py`

## Follow-ups

- Optional: add Video/Merge estimate lines when Auto-Video / Auto-Merge are on (defaults ~3/track export, ~10/merge).
