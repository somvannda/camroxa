# Alembic merge — web music credit refund heads

**Date:** 2026-08-17  
**Surfaces:** `platform_api`  
**Branch:** `feature/web-music-credits-hardening`

## Summary

Resolves multiple Alembic heads on sandbox by adding the missing parallel merge migrations from server history and a new merge revision `103_merge_credit_refund_heads` joining `102_credit_refund_idempotency` with `1f0ad008d202`.

## Test plan
- `alembic heads` shows single head `103_merge_credit_refund_heads` on sandbox after upgrade
