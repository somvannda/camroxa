# Credit-only release: creator program held out of main

**Date:** 2026-11-11
**Branch:** `release/credit-only`
**Surfaces:** whole repo (revert), platform_api (migration parent)
**Status:** implemented; production deploy pending

## Why

The credit fixes must reach production now, but production ships a **commit of
`origin/main`**, and `main` contains the creator program (merge `1260928c`,
migrations 186–196). That release is not ready to deploy. Shipping `main` as-is
would roll out the creator program as a side effect.

This commit reverts the creator-program merge so `main` is a credit-only
release. The creator work remains on its branches; nothing was lost.

## What this changes

- Reverts merge `1260928c` (`feat/creator-program`): creator services, routers,
  repositories, migrations **186–196**, tests, admin/creator UI, creator docs,
  and the `unslop` skill it introduced (including the AGENTS.md UI section it
  added).
- Re-points `197_pack_lot_ref_unique` from `down_revision = "196"` to
  `"185"`. It has never been applied through Alembic anywhere, so re-parenting
  is safe. The graph now has a **single head: 197**.

## Re-landing the creator program

1. Revert this revert (restores code and migrations 186–196).
2. Re-point the creator chain's first migration to follow `197`
   (e.g. `186.down_revision = "197"`). None of 186–196 has been applied in any
   environment, so editing the parent is allowed.
3. Deploy as usual.

Do not deploy the creator chain *before* 197 is applied, or the two branches
would fork and the credit migration would be skipped.

## Impact on production

None yet — this commit only changes `main`. The deployed production commit stays
`6a91258e` until the release deploy runs `185 → 197` (partial unique index +
migration-091 trigger drop).

The credit data repair from 2026-11-11 is independent of this and already
applied.
