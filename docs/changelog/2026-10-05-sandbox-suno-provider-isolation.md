# Sandbox Suno provider isolation + end-to-end verification

## Summary
The sandbox `platform_api` was configured to use the **production** musicapi
(`https://musicapi.camxora.com`) as its Suno provider, so any music test run
from the sandbox exercised production provider capacity. Repointed the sandbox
at `https://musicapi.sandbox.camxora.com`, provisioned a sandbox key, and
verified a real generation end-to-end.

## Product impact
None for end users. Sandbox music tests now stay inside the sandbox instead of
spending production provider credits.

## Technical impact
Sandbox configuration only (no repo schema change):
- Provisioned a musicapi API key on the **sandbox** musicapi
  (`sk_<uuid>`, name `platform-sandbox`, user `admin@example.com`, 100k credits;
  musicapi keys are `sha256`-hashed in `api_keys.key_hash`).
- Registered it in the platform key pool: `api_key_entries`
  (provider `suno`, label `sandbox-musicapi`, status `active`,
  `base_url = https://musicapi.sandbox.camxora.com`, value encrypted with
  `PLATFORM_ENCRYPTION_MASTER_KEY`).
- Set `key_pool_configs.base_url` for provider `suno` to the sandbox host.
  (`active_suno_key_values` filters keys by this base_url, so production keys
  are no longer selected on sandbox.)

## Verification (real generation)
Through the sandbox platform's active key against the sandbox musicapi:
- resolver poll: `pending x5 -> success`
- durable URL returned: `https://s3.us-east-005.backblazeb2.com/productions-camxora-song/...`
- `audio_storage_key = musicapi/clips/<clip>.mp3`
- musicapi job: type `music`, status `complete`, no error
- `recovery_audio` jobs created: **0**

This confirms the musicapi provider fixes: a real durable URL is parsed, no
`tempfile.aiquickdraw.com` URL is fabricated, and no recovery storm follows.

## Reproduce (sandbox)
1. Create an `api_keys` row on the sandbox musicapi (`sha256(sk_<uuid>)`,
   `credits > 0`).
2. Insert/update `api_key_entries` (provider `suno`, base_url
   `https://musicapi.sandbox.camxora.com`, value encrypted).
3. Set `key_pool_configs.suno.base_url` to the sandbox host.

## Follow-ups
- Make the sandbox Suno provider config reproducible (seed/deploy step) so it
  cannot drift back to production.
- The desktop-studio generation path is gated by a paid-plan requirement
  (`DESKTOP_PLAN_REQUIRED`); a sandbox e2e of that path needs a paid test user.

## Files touched
- Sandbox database/config only (no repo files).
