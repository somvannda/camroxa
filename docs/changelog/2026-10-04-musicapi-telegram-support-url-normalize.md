# musicapi: normalize Telegram support link to an absolute URL

## Summary

The user panel's **Get Support** sidebar link pointed at the panel origin
(`https://musicapi.camxora.com/@aistore168kh`, a 404) instead of Telegram. The
operator had stored the bare handle `@aistore168kh` in `brand.support_telegram_url`;
the dashboard renders that string directly as an `href`, so the browser resolved
it relative to the current origin.

`normalizeTelegramUrl()` now converts a bare handle (or scheme-less `t.me/...`
link) into `https://t.me/<handle>`, passing absolute `http(s)` URLs through
unchanged. It is applied on both read and save.

## Product impact

- "Get Support" in the user dashboard opens Telegram again.
- Existing stored values self-correct on read — no DB edit needed.
- Admins may enter either a full link or a bare handle; the admin UI documents
  the accepted input and shows the normalized value after save.

## Technical impact

- `musicapi/src/server.ts`
  - Added `normalizeTelegramUrl(raw)`.
  - `coerceBrand()` normalizes `support_telegram_url` when the brand document is
    loaded, so previously stored handles are fixed without a migration.
  - `mergeBrand()` normalizes on save, so future writes are stored as absolute URLs.
- `musicapi/web-admin/app/admin/settings/page.tsx`
  - Helper text under the Telegram field noting `@your_support` is saved as
    `https://t.me/your_support`.

No schema change, no migration.

## Files touched

- `musicapi/src/server.ts`
- `musicapi/web-admin/app/admin/settings/page.tsx`
- `docs/changelog/2026-10-04-musicapi-telegram-support-url-normalize.md`

## Migration / deploy

1. Deploy the `musicapi` core API (the normalization runs there).
2. Rebuild `web-admin` for the helper text (cosmetic); `web-user` needs no change,
   but the deploy ships the whole stack.
3. No migration.

## Tests

- `musicapi`: `npx tsc --noEmit` → clean.
- Live check after deploy: `GET https://musicapi.camxora.com/backend/settings`
  returns `support_telegram_url: "https://t.me/aistore168kh"`.

## Follow-ups

- None.
