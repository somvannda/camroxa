# Admin Job Queue metrics UI

**Date:** 2026-08-02  
**Status:** implemented  
**Branch:** `fix/api-phase1b-queue-followons`

## What

Admin portal page at `/job-queue` that polls `GET /api/v1/admin/job-queue/metrics` every 15s.

Shows:
- Queued depth / running / failed
- `/progress` p50·p95 latency samples
- Threshold alerts
- Status + job-type breakdown
- Busy worker locks

## Notes

`/progress` latency is per uvicorn worker process (same caveat as the API response `note`).
