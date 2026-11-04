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

The rows were encrypted with the production key. Without it the service refuses to
start, so the internal stems route cannot be exercised locally at all. Supplying or
guessing that key is out of scope — it is an environment secret, not a code gap.

Even with musicapi running, the last step needs a **real** clip id whose Suno account is
recorded (`findAssetAccountAny`), which a synthetic `audio_id_ok` cannot provide. So the
honest requirement is: a genuinely generated clip plus that key.

## What this means for the roadmap

W4.2 and the stems half of W4.3 are **environment-blocked, not code-blocked**. The UI,
the operation record, the credit charge, the token check and the error surfacing are all
in place and verified up to the gate they can reach. Nothing here should be "fixed" by
faking a clip id or a key.
