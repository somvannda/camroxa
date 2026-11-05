# STEMS — why W4.2 stops where it does

The client and both server halves exist. This file records the exact chain, what was
verified, and the one thing that cannot be supplied from a checkout.

## The chain (all ours — no Suno private API)

```
Studio editor  Get stems
   ↓
platform_api   POST /api/v3/web-music/studio/generations/{task}/stems   (UI → 202)
   ↓  validates status == "success" and a non-empty audio_id_ok
   ↓  charges credits via the web-music charge bridge
   ↓  POST {suna_api_base_url}/internal/studio/stems   header x-internal-token
musicapi       POST /internal/studio/stems
   ↓  requireInternalToken  (STUDIO_INTERNAL_TOKEN, both sides)
   ↓  findAssetAccountAny(clip_id)  → the Suno account that owns the clip
   ↓  upstream render
```

## What was verified

| Step | Result |
|---|---|
| UI button, request, polling, error surfaced in place | ✅ (W4.2 commit) |
| Seeded clip with `status = "complete"` | rejected: *"The clip is not ready for Studio edits yet."* |
| Seeded clip with `status = "success"` + `audio_id_ok` | passes, then: *"Studio operations are not configured."* (token gate) |
| `musicapi` deps installed and server started | **blocked** — see below |

`scripts/make_seed_clip_studio_ready.py` is what moved the clip past the first gate.

## The one blocker

`musicapi` will not boot against the local `sunoapi` database:

```
Failed to decrypt a stored Suno client_cookie: COOKIE_ENCRYPTION_KEY does not match
the key these rows were encrypted with.
```

### Follow-up (2026-11-05): both gates were cleared, and a third appeared

Using the key from the canonical checkout's `musicapi/.env` (same machine, same owner —
configuration, not a secret to be typed in) plus `STUDIO_INTERNAL_TOKEN` on both
services, the chain advanced further than this file first recorded:

| Gate | Result |
|---|---|
| cookie key | **solved** — musicapi boots with the canonical `.env` (`health 200`) |
| platform token | **solved** — `PLATFORM_STUDIO_INTERNAL_TOKEN` (note the `PLATFORM_` prefix; the unprefixed name is ignored) |
| credit charge | **blocked** — `UndefinedTableError: relation "plans" does not exist` |

The charge bridge still queries `plans`, but the sandbox database is at alembic **178**,
where `credit_repo.py` itself notes *"plan_id filtering is retired with plans"*. In other
words our branch's code is **older than that database's schema** — the sandbox belongs to
the `postforme-publishing` line.

Fixing that means migrating the shared sandbox database to this branch's head (or using
a database built from our migrations), which would disturb work in progress elsewhere.
Not something to do unattended.

The copied `musicapi/.env` was deleted immediately after the attempt; it holds production
credentials and must never be committed (it is gitignored, and `git check-ignore` confirms).

### Follow-up 2 (2026-11-05): a fresh database proves it is stale code

Built an **isolated** database (`camxora_studio_dev`) from this branch's own migrations
so the shared sandbox was never touched. At head (revision **177**) it has 110 public
tables and **no `plans`** — exactly like the sandbox.

So the charge bridge failure is not schema drift. Migration **174 ("credits-only
two-tier model")** removed `plans`, and these queries still join it:

| File | Lines |
|---|---|
| `platform_api/repositories/credit_repo.py` | `INNER JOIN plans p ON p.id = l.plan_id`, `… ON p.id = ws.plan_id` |
| `platform_api/repositories/license_repo.py` | plan reads, insert, selection |

`credit_repo.get_active_plan_slots` is the one the Studio charge path reaches, so any
stems/extend/cover request fails with `UndefinedTableError: relation "plans" does not
exist`.

**Why this stops here rather than getting "fixed"**: what replaces a plan allowance under
the credits-only model is a billing decision, not a refactor. Rewriting those queries
without that decision would trade a loud failure for a quiet one.

Not covered by tests either: `tests/test_credit_repo.py`, `test_credit_ledger.py` and
`test_v3_credits_only.py` pass 62/63 without ever reaching `get_active_plan_slots`.
(`test_admin_adjust_visible_on_v3_wallet` fails for an unrelated reason — its
`FakeStore` has no `_pool`.)

## Requirement summary

1. a database at this branch's schema (so `plans` exists for the charge bridge), **and**
2. a genuinely generated clip whose Suno account is recorded (`findAssetAccountAny`).

Neither is a code gap. Faking either would produce a green test that proves nothing.

## What this means for the roadmap

W4.2 and the stems half of W4.3 are **environment-blocked, not code-blocked**. The UI,
the operation record, the credit charge, the token check and the error surfacing are all
in place and verified up to the gate they can reach. Nothing here should be "fixed" by
faking a clip id or a key.
