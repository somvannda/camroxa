# musicapi: stop false "UNHEALTHY" Telegram alerts after deploys

## Summary

The sandbox host (`vmi2746998`) paged ``musicapi UNHEALTHY:
http://127.0.0.1:4003/health did not answer`` after deploys, even though the API
came back seconds later. Two independent defects were responsible:

1. **The probe raced the API boot.** `camxora-musicapi-remote.sh` runs the
   healthcheck unit immediately after restarting the stack
   (`systemctl start camxora-musicapi-healthcheck.service`). The probe made a
   single `curl` with no retry, so it caught the API while it was still binding
   `:4003` and reported "did not answer".
2. **The alert dedupe was broken by file ownership.** `musicapi-healthcheck.sh`
   runs as `camxora`, but `/opt/camxora/.musicapi-health.state` had been created
   as `root:root` mode `644` (a prior run as root). The script could not
   overwrite it (`WARN: cannot write ...`), so `prev` always read `ok`:
   every failing probe looked like a fresh `ok -> down` transition and paged
   again, and a `RECOVERED` message could never be sent.

## Product impact

- Operators no longer receive "UNHEALTHY" pages for redeploy/restart blips.
- A genuine outage still pages once, and now reaches a `RECOVERED` message when
  the API returns.
- HTTP-level failures (e.g. a non-200 from `/health`) are reported as
  `returned HTTP <code>: ...` instead of the misleading "did not answer".

## Technical impact

- `scripts/deploy/musicapi-healthcheck.sh`
  - New `probe_health()` retries `/health` up to `HEALTH_RETRIES` (default `6`)
    times, `HEALTH_RETRY_DELAY` (default `5s`) apart, before declaring a
    failure — enough to cover API boot after a restart.
  - Uses `curl -w '%{http_code}'` plus the body, so "no HTTP response" and a
    non-200/bad body are distinguished in the alert text.
  - New `write_state()` writes `${STATE_FILE}.$$` and `mv -f`s it into place.
    Rename only needs write access to the directory (`/opt/camxora`, owned by
    `camxora`), so a stale root-owned state file is replaced rather than
    blocking every write.

No route, schema, or environment change. `HEALTH_RETRIES`/`HEALTH_RETRY_DELAY`
are optional overrides; defaults ship via the systemd `EnvironmentFile` being
absent for these keys.

## Files touched

- `scripts/deploy/musicapi-healthcheck.sh`
- `docs/changelog/2026-10-04-musicapi-healthcheck-false-alerts.md`

## Migration / deploy

1. Deploy `musicapi` (the tarball carries `scripts/deploy/`) to the affected
   host, or copy `scripts/deploy/musicapi-healthcheck.sh` into
   `/opt/camxora/repo/scripts/deploy/`. No unit file change.
2. Optional, immediate stop-gap while the old script is still installed:
   `chown camxora:camxora /opt/camxora/.musicapi-health.state`
   The new atomic write also self-heals ownership on the next write.

## Tests

- `bash -n scripts/deploy/musicapi-healthcheck.sh` → clean.
- On sandbox `vmi2746998`: `write_state ok` as `camxora` replaced a
  `root:root 644` state file and left it `camxora:camxora`.
- On sandbox `vmi2746998`: `probe_health` returned `{"ok":true,"accounts":2,"jobs":0}`
  against the live `127.0.0.1:4003`, and reported
  `... did not answer after 2 attempts` against `127.0.0.1:1` with
  `HEALTH_RETRIES=2`, `HEALTH_RETRY_DELAY=0`.

## Follow-ups

- Optionally have the healthy path also call `write_state` each run, so a stale
  root-owned file is reclaimed without waiting for the first failure. Not needed
  with the rename-based write, which already replaces it on the first write.
