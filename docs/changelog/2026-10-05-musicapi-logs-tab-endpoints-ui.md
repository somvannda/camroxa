# musicapi: exact endpoint tabs on the usage logs + sunoapi.org UI parity

## Summary

The dashboard usage logs (`/dashboard/logs`) filtered tabs with **substring**
`ILIKE` patterns (`audio` → `%audio%`), so a job's endpoint could appear on the
wrong tab. `recovery_audio` leaked into the **audio** tab, and
`mp4_generate` / `midi_generate` / `voice_generate` matched an `audio` pattern
containing `"generate"`. At the same time, endpoints that matched no pattern at
all (`extend`, `cover`, `mashup`, `add_vocals`, `add_instrumental`, `remaster`,
`boost_style`, `upload_*`, and the `*_detail` routes) were invisible on every
tab. This switches the tabs to **exact endpoint sets** and aligns the page
chrome with sunoapi.org.

## Product impact

- **No more cross-tab leakage:** `recovery_audio` / `recovery_detail` only
  appear under **recovery audio**; MP4/MIDI/voice jobs no longer sit in
  **audio**.
- **No more invisible jobs:** every endpoint value written to `usage_logs`
  now maps to exactly one tab (verified across all 225 rows in the local DB).
- **Closer sunoapi.org parity:** segmented tab bar, dismissible Log Retention
  notice, dot + lowercase status pills, a `Credits Consumed` header, and
  numbered pagination.
- Retention copy states our real policy (media kept while the account is
  active; usage logs up to 12 months) rather than sunoapi.org's 14-day claim.

## Technical impact

- `musicapi/src/server.ts` — `GET /me/logs/page` accepts an exact
  `endpoints` query param, applied as `= ANY($n::text[])` to both the
  `usage_logs` ledger and the in-flight `jobs` half of the UNION. The existing
  substring `endpoint` param is unchanged for backward compatibility.
- `musicapi/web-user/app/dashboard/logs/page.tsx`
  - `FILTER_TABS` + `TAB_PATTERNS` replaced by a single `TABS` array carrying
    an exact `endpoints` list per tab; the load request sends `endpoints=`.
  - Retention notice (localStorage `logs_retention_dismissed`, 24h),
    segmented tab bar, dot status pills, `pageItems()` numbered pagination.

No schema change.

## Files touched

- `musicapi/src/server.ts`
- `musicapi/web-user/app/dashboard/logs/page.tsx`
- `docs/changelog/2026-10-05-musicapi-logs-tab-endpoints-ui.md` (this file)

## Migration / deploy

- No migration. Deploy via the normal sandbox-first chain
  (`scripts/deploy/sync_musicapi_sandbox.py`, then
  `scripts/deploy/deploy_musicapi_production.py --yes` on an explicit ask).

## Tests

- `npm run typecheck` (musicapi) → clean.
- `npm run typecheck` (web-user) → clean.
- ESLint on the changed page → clean.
- SQL partition check over all 225 `usage_logs` rows: exact sets cover every
  row, no overlap; `recovery_audio` absent from the audio set.
- Live API (`/me/logs/page`): audio = 108 rows with no `recovery_audio`;
  recovery = 12 rows; the legacy `endpoint=audio` substring still returns the
  9 `recovery_audio` rows (the original bug).
- Live UI (seeded 216-log account): audio tab renders with no `recovery_audio`;
  recovery tab renders the 12 recovery rows.

## Follow-ups

- The inline `Actions` (MP3/WAV/MIDI/MP4) column is kept even though
  sunoapi.org has no such column; it can be folded into the Result modal if an
  exact column match is wanted.
