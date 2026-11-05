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
`test_v3_credits_only.py` passed 62/63 without ever reaching `get_active_plan_slots`
(the one failure was a `FakeStore` fixture gap, since repaired).

### Follow-up 3: the root cause is a retired billing bridge on a live path

Traced the traceback rather than guessing:

```
web_music_service.py:3703   charge = await self._web_music_charge_bridge().charge(...)
v3/web_music_charge.py:125  charge(...)
v3/web_music_charge.py:108  plan = await self._store.resolve_charge_plan(user_id)
v3/store.py:172             resolve_charge_plan → get_plan_for_user → FROM plans
                            → UndefinedTableError
```

`v3/web_music_charge.py` is the **pre-credits-only** bridge — its own header says
*"One charge model: amount = plan.<op>_credits"* — while `v3/credits_only_billing_service.py`
is the replacement that the migration series moved to. The Studio operation path still
calls the retired one.

That is why `get_active_plan_slots` looked like the culprit: it is a symptom. The real
defect is **two billing implementations coexisting, with Studio wired to the old one**.

Fixing it means repointing Studio's charge, refund and quote at the credits-only service
and re-deciding where an operation's price comes from (the `pricing` table, per project
rules). That is money semantics — the one area where a guess is worse than a blocker.

**Do not "fix" it by recreating a `plans` row or a fake plan allowance.** It would make
the error disappear while silently pricing Studio operations from a table the product no
longer has.

### Follow-up 4 (2026-11-05): the rebind is in — the chain now ends at the account guard

Owner decision: **narrow scope, studio operations only.** Music/lyric/style keep their
existing plan lookup; studio ops price from `credit_pricing` through
`credits_only_billing_service` and never read `plans`.

What changed, in one file (`platform_api/services/v3/web_music_charge.py`):

| Path | Before | After |
|---|---|---|
| `quote_credits` | always `store.resolve_charge_plan()` → `FROM plans` | resolves a plan **only for non-studio ops**; studio ops pass `plan_id=None` |
| `charge` | always ran the free-model scope check (needs a plan) | studio ops skip it — they carry no Suno model and are priced flat |
| `refund` | already path/amount based | unchanged (reverses the recorded debit via the credits-only service) |

Prices come from the `credit_pricing` rows that already existed: `suno/studio_edit`
120,000 units = **12 credits**, `suno/studio_stems_2` 120,000 = **12**,
`suno/studio_stems_12` 600,000 = **60** (CREDIT_SCALE = 10,000).

Verified live (platform_api from this worktree, sandbox DB, `mode=stems`):

| Step | Evidence |
|---|---|
| Quote | `GET /api/v3/web-music/studio/pricing` → `{"edit":12,"stems_2":12,"stems_12":60}` |
| Charge | `credit_transactions` debit 600,000 units, reason `v3_studio_stems_12`, metadata `quote_source=credit_pricing`, `product=web_music` |
| Operation row | `studio_operations.credits_charged=60`, `charge_path=v3`, `charge_op=studio_stems_12`, `charge_ref=<op id>` |
| Forward | `POST /internal/studio/stems` reached musicapi |
| New gate | musicapi `409` → **"The source clip's Suno account is not recorded."** |
| Refund | `v3_refund_studio_stems_12` +600,000 units, `refunded_at` set, wallet back to its pre-charge balance |

So the plans failure is gone, the money path is real, and the **only** remaining stop is
the one this file always predicted: `findAssetAccountAny` needs a clip that a real Suno
account actually produced. The seeded `sandbox-clip-ok` is not one, and no amount of
schema work will change that.

## Requirement summary

1. ~~a database at this branch's schema (so `plans` exists for the charge bridge)~~ —
   removed; studio pricing no longer consults a plan table.
2. **A genuinely generated clip whose Suno account is recorded** (`asset_owners`, or a
   `jobs.result_json` containing the clip id, in the `sunoapi` database).

Only #2 remains. Faking it would produce a green test that proves nothing.

## What this means for the roadmap

The charge half of W4.2 and the stems half of W4.3 are **done and verified**: quote,
debit, operation record, forward, failure refund. Receiving an actual stem set needs one
real generated clip in the sandbox; that is an environment prerequisite, not a code gap.

