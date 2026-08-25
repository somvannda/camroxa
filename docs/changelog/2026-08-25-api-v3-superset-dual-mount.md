# API v3 full surface (dual-mount) + sandbox restore

## Summary

`/api/v3` is now the canonical full API surface for Camxora: former `/api/v1` routers, CutLuy billing (`/subscriptions`, `/credits`, `/topups`), CutLuy webhooks, and the unified wallet (`v3_billing`) are all available directly under `/api/v3/...`.

`/api/v1` and `/api/v2` remain mounted temporarily for rollback. Clients should migrate to `/api/v3` only.

## Server

- Dual-mount every former v1 router under `api_v1_prefix` and `api_v3_prefix` (including `webhooks_cutluy`).
- Mount CutLuy billing under `/api/v2` (temporary) and `/api/v3` (canonical) with resource prefixes `/subscriptions|credits|topups` (fixed subscriptions router: no nested `/v2/`).
- Keep `v3_billing` on `/api/v3` only (wallet quote/charge/grants/`me/credits`).
- Health under root, `/api/v1`, and `/api/v3`.
- `http_paths.strip_api_version_prefix` recognizes `/api/v3`.

## Sandbox

Redeploy restores wallet `/api/v3` that was lost when an incomplete `main.py` (without `v3_billing`) was hotfixed earlier, without regressing `/api/v2/subscriptions/plans`.
