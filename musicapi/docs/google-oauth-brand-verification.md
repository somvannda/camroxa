# Google OAuth brand verification — fix runbook

Google's OAuth consent screen ("branding") review rejected the app with four
issues. This runbook maps each issue to its root cause and the exact action.

| # | Reviewer message | Root cause | Fix |
|---|------------------|-----------|-----|
| 1 | Home page URL is not registered to you | No `google-site-verification` meta tag is served; `musicapi.camxora.com` was never verified in Search Console for the OAuth project's Google account | Search Console verification (below) + wait 24 h |
| 2 | Privacy policy has insufficient content | Cloudflare Email Address Obfuscation rewrote our contact addresses into `[email protected]` / `/cdn-cgi/l/email-protection#…`, so the policy appears to have no reachable contact. Policy text has also been expanded. | Disable email obfuscation + deploy the expanded policy |
| 3 | Home page is behind a login page | The root layout rendered the (closed) sign-in `<dialog>` into **every** page's HTML, so a reviewer's crawler saw a sign-in form on `/`. A `401` from any API call also hard-redirected public pages to `/login`. | Code fixed: modal renders only when opened; public pricing fetch never redirects on 401 |
| 4 | Home page does not explain the app | Purpose copy exists, but the same crawl problems (1–3) prevented it from being read | Code fixed: explicit purpose + Google-data statement above the fold |

## 1. Verify domain ownership (Search Console)

Use the **same Google account that owns the OAuth consent screen / Cloud project.**

1. Open <https://search.google.com/search-console> → **Add property** → **URL prefix**.
2. Enter `https://musicapi.camxora.com/` (exactly, with the trailing slash).
3. Choose **HTML tag** verification and copy the `content` value (the token after
   `google-site-verification=`).

   *Alternative:* use a **DNS TXT** record. In Cloudflare DNS add a `TXT` on
   `musicapi` with value `google-site-verification=<token>`. DNS verification
   usually does not require a redeploy.

4. Put the token in the deploy secrets and redeploy so it is baked into
   `web-user/.env.production` (the deploy script writes it from
   `MUSICAPI_GOOGLE_SITE_VERIFICATION`):

   ```bash
   # .deploy/secrets.production.env
   MUSICAPI_GOOGLE_SITE_VERIFICATION=<token-from-search-console>
   # then:
   python scripts/deploy/deploy_musicapi_production.py --yes
   ```

5. Confirm the tag is live **before** clicking Verify:

   ```bash
   curl -s https://musicapi.camxora.com/ | grep -o 'google-site-verification[^>]*'
   # => google-site-verification" content="<token>"
   ```

6. Back in Search Console click **Verify** (should pass immediately).
7. **Wait 24 hours** before retrying the OAuth brand verification — Google's
   systems cache ownership for up to a day.

## 2. Fix the privacy policy rendering (Cloudflare)

Cloudflare's **Scrape Shield → Email Address Obfuscation** is on for the zone and
rewrites every address in the HTML. Disable it so `privacy@camxora.com`,
`support@camxora.com`, and `legal@camxora.com` render as text/links:

1. Cloudflare dashboard → select the `camxora.com` zone → **Scrape Shield**.
2. Turn **Email Address Obfuscation** **off**.
3. If you must keep it on globally, add a Configuration Rule scoped to
   `http.host eq "musicapi.camxora.com"` that skips email obfuscation for
   `/privacy`, `/terms`, `/data-deletion`.
4. Purge cache for those URLs (Caching → Configuration → Purge).

The policy itself now adds: an "At a glance" summary (what/why/sharing/controls),
an explicit "we do not use Google user data to train AI models" statement, and
concrete retention periods.

## 3. Keep the public pages crawlable

Do **not** put `/`, `/privacy`, `/terms`, or `/data-deletion` behind a Cloudflare
**Managed Challenge** or "Under Attack" mode — Google's verifier must fetch them as
an anonymous browser.

1. Cloudflare → **Security → Bots**: confirm "Under Attack Mode" is **off**.
2. Cloudflare → **Security → WAF → Managed rules / Rate rules**: ensure no rule
   challenges these paths. If you use a custom rule, add an exception:
   `(http.request.uri.path in {"/" "/privacy" "/terms" "/data-deletion" "/docs"})`.
3. Allow verified bots (Googlebot/Google's verification crawler) under
   **Security → Bots → Verified bots**.

The app now also ships `robots.txt` (allows `/`, blocks `/dashboard/`, `/admin/`,
`/backend/`) and `sitemap.xml`.

## 4. What changed in code (already on this branch)

- `web-user/components/auth-modal.tsx` — the sign-in dialog renders only when
  opened, so no sign-in form appears in the server-rendered HTML of public pages.
- `web-user/lib/api.ts` — `apiFetch()` gained `allowUnauthenticated`; a `401` on a
  public call no longer redirects to `/login`.
- `web-user/app/page.tsx` — explicit purpose copy + Google-data statement + "no
  account needed to browse"; public pricing fetch uses `allowUnauthenticated`.
- `web-user/app/privacy/page.tsx` — "At a glance" summary, no-AI-training
  statement, concrete retention periods.
- `web-user/app/layout.tsx` — richer title/description/OpenGraph/canonical; keeps
  the `GOOGLE_SITE_VERIFICATION` meta-tag support.
- `web-user/app/robots.ts`, `web-user/app/sitemap.ts` — new.
- `web-user/.env.example`, `.deploy/secrets.production.env.example` — document
  `MUSICAPI_GOOGLE_SITE_VERIFICATION`.

## 5. Re-submit checklist

- [ ] `MUSICAPI_GOOGLE_SITE_VERIFICATION` set and present in the live home page `<head>`.
- [ ] Search Console shows the property **Verified**.
- [ ] `curl -s https://musicapi.camxora.com/ | grep -c 'Continue with Google'` → `0`
      (no sign-in form in the public HTML).
- [ ] Home page explains the app's purpose and how Google data is used (visible without login).
- [ ] `https://musicapi.camxora.com/privacy` shows real `privacy@camxora.com` /
      `support@camxora.com` addresses and the expanded sections.
- [ ] Cloudflare email obfuscation off; no bot challenge on public paths; cache purged.
- [ ] Wait 24 h after Search Console verification, then retry the brand review.
