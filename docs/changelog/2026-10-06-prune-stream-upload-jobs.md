# Pruned duplicate `stream_upload_jobs` backlog

## Summary
Re-delivered Suno callbacks and desktop reconcile historically inserted many
duplicate job rows per `(suno_task_id, kind)` — one task carried 3,755 + 3,740
rows. The application guard and DB unique index (PR #342) stop *new* duplicates;
this one-off prune removed the historical backlog.

## Product impact
None. Admin upload-job counts and the table now reflect reality; no audio or B2
copy was touched.

## What was done
- `scripts/deploy/prune_stream_upload_jobs_production.py` (dry-run by default)
  keeps exactly one row per `(suno_task_id, kind)` for `mp3_ok`/`mp3_alt`,
  preferring a successful, B2-backed, newest row. Rows with a NULL
  `suno_task_id` (cover jobs) and `pending` rows are never touched; no
  task+variant loses its only row.
- Production: backed up the table with `pg_dump` to
  `/tmp/stream_upload_jobs_<stamp>.sql.gz`, then deleted in 5,000-row batches.

## Result
- Total rows **61,824 → 15,718** (46,106 duplicates removed).
- `distinct_task_kind` unchanged at **14,104** (verified no task+variant lost its
  only row).
- FK references pointing *to* `stream_upload_jobs`: 0.

## Files touched
- `scripts/deploy/prune_stream_upload_jobs_production.py`
