# musicapi: Google OAuth brand-verification compliance fixes

## Summary

Google's OAuth consent-screen ("branding") review rejected `musicapi.camxora.com`
with four issues: domain ownership not verified, privacy policy "insufficient",
home page "behind a login page", and home page "does not explain the app".

The two page-content complaints were partly caused by how the site rendered:
the root layout mounted the sign-in modal on **every** page (including
`/`, `/privacy`, `/terms`), so the server-rendered HTML for public pages
contained a full sign-in form; and `apiFetch()` hard-redirected any `401` to
`/login`, which could bounce a public visitor off the landing page. The policy's
contact addresses were also being masked by Cloudflare Email Obfuscation
(`[email protected]` / `/cdn-cgi/l/email-protection#…`).

This change makes the public pages unmistakably public, expands the privacy
policy, documents/verifies the Search Console token path, and adds robots/sitemap
routes. Domain ownership itself remains an ops step (Search Console + Cloudflare),
documented in `musicapi/docs/google-oauth-brand-verification.md`.

## Product impact

- The home page renders no sign-in form until a user actually opens it, so
  Google's reviewer (and any crawler) sees a public marketing/docs page.
- Public API calls can no longer bounce anonymous visitors to `/login`.
- The home page states the app's purpose and how Google data is used, above the fold.
- The privacy policy gains an "At a glance" summary, an explicit "we do not use
  Google user data to train AI models" statement, and concrete retention periods.
- New `robots.txt` and `sitemap.xml` expose the public pages to crawlers.

## Technical impact

- `musicapi/web-user/components/auth-modal.tsx`
  - Renders `null` while closed; opens the native `<dialog>` on demand.
  - Removed the unused `error`/`loading` state and its set-state-in-effect.
- `musicapi/web-user/lib/api.ts`
  - `apiFetch(path, init, { allowUnauthenticated })`; a `401` only redirects to
    `/login` when `allowUnauthenticated` is not set.
- `musicapi/web-user/app/page.tsx`
  - Purpose copy + Google-data statement + "no account needed to browse".
  - Pricing fetch uses `{ allowUnauthenticated: true }`.
- `musicapi/web-user/app/privacy/page.tsx`
  - "At a glance" block, Google no-training statement, retention periods;
    effective date bumped to 2026-10-04.
- `musicapi/web-user/app/layout.tsx`
  - Descriptive title/description/OpenGraph/canonical; keeps
    `GOOGLE_SITE_VERIFICATION` → `<meta name="google-site-verification">`.
- `musicapi/web-user/app/robots.ts`, `musicapi/web-user/app/sitemap.ts` — new.
- `musicapi/web-user/.env.example`, `.deploy/secrets.production.env.example` —
  document `MUSICAPI_GOOGLE_SITE_VERIFICATION`.
- `musicapi/docs/google-oauth-brand-verification.md` — new ops runbook.

## Files touched

- `musicapi/web-user/components/auth-modal.tsx`
- `musicapi/web-user/lib/api.ts`
- `musicapi/web-user/app/page.tsx`
- `musicapi/web-user/app/privacy/page.tsx`
- `musicapi/web-user/app/layout.tsx`
- `musicapi/web-user/app/robots.ts` (new)
- `musicapi/web-user/app/sitemap.ts` (new)
- `musicapi/web-user/.env.example`
- `.deploy/secrets.production.env.example`
- `musicapi/docs/google-oauth-brand-verification.md` (new)
- `docs/changelog/2026-10-04-musicapi-google-oauth-brand-verification.md`

## Migration / deploy

1. No schema change, no migration.
2. Set `MUSICAPI_GOOGLE_SITE_VERIFICATION` in `.deploy/secrets.production.env`,
   then run the normal musicapi deploy (rebuilds `web-user`).
3. Verify the meta tag is live, then click Verify in Search Console.
4. Cloudflare: disable Email Address Obfuscation and ensure no bot challenge on
   the public paths; purge cache.
5. Wait 24 h, then retry the OAuth brand review.

## Tests

- `npm run typecheck` (web-user) → clean.
- `npx eslint` on the touched files → no errors (only pre-existing warnings).
- `npm run build` (web-user) → succeeds; `/robots.txt` and `/sitemap.xml` generated.
- Prerendered HTML checks:
  - `index.html` contains "without signing in" and "never access Gmail", and does
    **not** contain "Continue with Google".
  - `privacy.html` contains "At a glance" and the retention section.

## Follow-ups

- Confirm the reviewer sees the real contact emails after Cloudflare Email
  Obfuscation is disabled (re-check `curl https://musicapi.camxora.com/privacy`).
