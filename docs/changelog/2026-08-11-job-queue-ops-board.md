# 2026-08-11 — Admin Job Queue ops board

## Summary

The admin Job Queue page was aggregate-only (counts + opaque `hostname:pid` locks). It is now a live ops board: who is running what, which worker stage is busy, durable job failures with error text, and related `image_jobs` failures (SLAI/provider) that often never appear as `job_queue.failed`.

## Surfaces

- **Platform API**: `GET /api/v1/admin/job-queue/jobs`, `GET /api/v1/admin/job-queue/image-failures`; enriched `workers_busy` on metrics; worker id includes `CAMXORA_WORKER_NAME` / stage
- **Admin portal**: `/job-queue` rebuild (tabs, filters, busy workers table, image failure strip)
- **Deploy units**: systemd stage workers set `CAMXORA_WORKER_NAME=draft@%i` / `suno@%i` / `images@%i`

## Not included

- Retry / cancel / requeue actions (v2)
- systemd heartbeat inventory of idle workers
- Production deploy (sandbox only unless requested)
