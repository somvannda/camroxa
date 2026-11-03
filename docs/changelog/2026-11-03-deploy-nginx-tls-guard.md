# A full production deploy could finish with nginx serving HTTP only

**Date:** 2026-11-03
**Surfaces:** `scripts/deploy` (deploy tooling), `platform_api` (tests)
**Migration:** none

---

## Incident

A full `deploy_production.py` run on 2026-11-03 reported success while leaving
production **without TLS**. `api.camxora.com` and `admin.camxora.com` served a
certificate that did not match the hostname, so the API was healthy on
`127.0.0.1:8100` (`local_api=200`) but unreachable over HTTPS. The deploy's only
hint was `WARN: API health check failed`; it still exited 0.

Impact: the public API and admin console were down for TLS clients until the
canonical template was re-applied by hand.

## Root cause

`camxora-production-remote.sh` bootstraps a minimal **HTTP-only**
`/etc/nginx/sites-available/camxora-production`, then applies the uploaded HTTPS
config inside a conditional:

```bash
if [[ -f /tmp/nginx-camxora-production.conf && -f /etc/letsencrypt/live/api.camxora.com/fullchain.pem ]]; then
  ...
fi
```

When either file is absent the block is skipped **silently**: no log line, no
non-zero exit, and the HTTP-only bootstrap remains installed. The bootstrap is
also missing the `app.camxora.com` vhost, so successful runs of that path lose a
host as well.

## Fix

Three layers, so no single false condition can ship a broken edge again:

1. **`scripts/deploy/nginx_guard.py`** (new) — pure-text check:
   `missing_tls_hosts(conf)` returns every required host with no
   `listen 443` + `ssl_certificate` block. Brace-aware, because the config
   contains nested `location` blocks and commented-out `server {` examples.
2. **`deploy_production.py`** — `ensure_https_config()` re-uploads and re-applies
   the committed `nginx-camxora-production.conf`, reloads nginx, reads the
   applied file back, and fails the deploy (`DEPLOY_VERIFY_FAILED`) if any
   required host lacks TLS. It runs **even when the remote script exits non-zero**,
   because those fatal paths exit *after* the HTTP-only bootstrap is already in
   place.
3. **`camxora-production-remote.sh`** — the HTTPS apply is no longer a silent
   conditional: a missing certificate or missing uploaded config is a `FATAL`
   with a non-zero exit, and the applied site is asserted to contain
   `ssl_certificate`. The health check also probes
   `https://api.camxora.com/health`, not only the loopback.

## Product/ops impact

- A deploy can no longer report success while production serves HTTP only.
- A first-time bootstrap where certbot has not yet issued a certificate now
  **fails loudly** instead of leaving an HTTP-only site; fix DNS, re-run.
- No change to what gets shipped when the deploy is healthy.

## Files touched

- `scripts/deploy/nginx_guard.py` (new)
- `scripts/deploy/deploy_production.py` — `ensure_https_config()` + mandatory call
- `scripts/deploy/camxora-production-remote.sh` — fatal guards, TLS assertion, HTTPS health probe
- `platform_api/tests/test_deploy_nginx_tls.py` (new) — 5 tests

## Tests

`platform_api/tests/test_deploy_nginx_tls.py`:

- the committed template covers every required host;
- the exact HTTP-only bootstrap shape is rejected;
- a config missing `app.camxora.com` is reported;
- `listen 443` without `ssl_certificate` is rejected;
- custom required-host lists are honoured.

Combined with `test_release_source.py` and `test_migrations_runner.py`: 19 passed.
`bash -n camxora-production-remote.sh` clean; `check_deploy_hygiene.py` still
reports the same 4 verified sources and 5 known legacy scripts.

## Follow-ups

- The deploy tooling still carries pre-existing `E701`/`E702` style findings in
  `deploy_production.py`; untouched here to keep the diff focused.
- Consider asserting `https://` reachability for `admin.`/`app.` in the same
  post-deploy check, not just the API health endpoint.
