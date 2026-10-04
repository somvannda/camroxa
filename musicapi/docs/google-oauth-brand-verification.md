# Google OAuth brand verification — fix runbook

Google's OAuth consent screen ("branding") review rejected the app with four
issues. This runbook maps each issue to its root cause and the exact action.

| # | Reviewer message | Root cause | Fix |
|---|------------------|-----------|-----|
| 1 | Home page URL is not registered to you | No `google-site-verification` meta tag is served; `musicapi.camxora.com` was not yet verified in Search Console for the OAuth project's Google account | **Resolved** — ownership verified via the deployed HTML file `web-user/public/googlecc93aaa6b03dea9f.html` (plus a DNS TXT and a Domain property). See §1 |
| 2 | Privacy policy has insufficient content | Cloudflare Email Address Obfuscation rewrote our contact addresses into `[email protected]` / `/cdn-cgi/l/email-protection#…`, so the policy appears to have no reachable contact. Policy text has also been expanded. | Disable email obfuscation + deploy the expanded policy |
| 3 | Home page is behind a login page | The root layout rendered the (closed) sign-in `<dialog>` into **every** page's HTML, so a reviewer's crawler saw a sign-in form on `/`. A `401` from any API call also hard-redirected public pages to `/login`. | Code fixed: modal renders only when opened; public pricing fetch never redirects on 401 |
| 4 | Home page does not explain the app | Purpose copy exists, but the same crawl problems (1–3) prevented it from being read | Code fixed: explicit purpose + Google-data statement above the fold |

## 1. Verify domain ownership (Search Console) — ✅ done

Ownership is verified with the **HTML-file method**. The file is committed at
`web-user/public/googlecc93aaa6b03dea9f.html` and served at
<https://musicapi.camxora.com/googlecc93aaa6b03dea9f.html>, returning:

```
google-site-verification: googlecc93aaa6b03dea9f.html
```

A `google-site-verification` DNS TXT record on `musicapi.camxora.com` and a
**Domain property** for `camxora.com` are also in place, so the `https`/`http`,
`www`/non-`www` and subdomain variations are all covered.

> The property was added under the Google account **somvannda@gmail.com**, which
> must be the same account that owns the OAuth consent screen / Cloud project.

### Fallback: HTML meta tag

The app also supports the **HTML tag** method if the HTML file is ever removed.
`web-user/app/layout.tsx` renders `<meta name="google-site-verification">` from
`process.env.GOOGLE_SITE_VERIFICATION`, which the deploy script bakes in from the
`MUSICAPI_GOOGLE_SITE_VERIFICATION` secret (currently empty):

```bash
# .deploy/secrets.production.env
MUSICAPI_GOOGLE_SITE_VERIFICATION=<token-from-search-console>
python scripts/deploy/deploy_musicapi_production.py --yes
```

Confirm the tag is live **before** clicking Verify:

```bash
curl -s https://musicapi.camxora.com/ | grep -o 'google-site-verification[^>]*'
# => google-site-verification" content="<token>"
```

### Sitemap

`https://musicapi.camxora.com/sitemap.xml` was submitted in Search Console
(Oct 2026) and is also advertised from `robots.txt`. Googlebot fetches it with
`200` / `application/xml`. If Search Console reports "Couldn't fetch", allow
24–48 h for the first read before troubleshooting.

> **Wait 24 hours** after any ownership change before retrying the OAuth brand
> verification — Google's systems cache ownership for up to a day.

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

- [x] Domain ownership verified (HTML file `googlecc93aaa6b03dea9f.html` served from `web-user/public/`; DNS TXT + Domain property also in place).
- [x] Search Console shows the property **Verified** (added under somvannda@gmail.com).
- [x] `sitemap.xml` submitted (allow 24–48 h for the first read).
- [x] `curl -s https://musicapi.camxora.com/ | grep -c 'Continue with Google'` → `0`
      (no sign-in form in the public HTML). Verified Oct 2026.
- [x] Home page explains the app's purpose and how Google data is used (visible without login). Verified Oct 2026.
- [ ] `https://musicapi.camxora.com/privacy` shows real `privacy@camxora.com` /
      `support@camxora.com` addresses and the expanded sections.
- [ ] Cloudflare email obfuscation off; no bot challenge on public paths; cache purged.
- [ ] Wait 24 h after Search Console verification, then retry the brand review.
