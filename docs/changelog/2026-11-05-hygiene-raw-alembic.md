# Hygiene check: no raw Alembic CLI in deploy scripts

**Date:** 2026-11-05
**Surfaces:** `scripts/deploy`, `platform_api` (tests)
**Migration:** none

---

## Why

`#480` routed `camxora-production-remote.sh` through
`platform_api.migrations.upgrade` so deploy migrations take the same advisory
lock as the API startup runner. But **15 other deploy scripts** still call the
Alembic CLI directly — including a bare `stamp`, which advances
`alembic_version` without applying DDL. That is the exact shape of the `178`
incident: a revision recorded, its column never altered.

A one-time fix decays. This adds the rule that stops it growing back.

## Change

`check_deploy_hygiene.py` gains a second finding type:

```
RAW ALEMBIC scripts/deploy/thing.py:42  runs the Alembic CLI; use
`python -m platform_api.migrations.upgrade` so the advisory lock applies
```

- Detects `alembic upgrade` / `alembic stamp` at a command position — after
  `&&`, `;`, or at line start, optionally behind `sudo` or a path prefix.
- Ignores prose: comments, docstrings and `journalctl | grep -E '...alembic
  upgrade...'` inspection lines do not match, so the check stays about
  *execution*.
- **16 pre-existing offenders are allowlisted** (`KNOWN_LEGACY_RAW_ALEMBIC`), so
  `--strict` stays green today while `--changed-only` fails as soon as someone
  edits one of them or adds a new script.

## Behaviour

| Mode | Raw Alembic in a legacy script | Raw Alembic in a new/changed script |
|---|---|---|
| default (report) | listed as legacy | listed as blocking |
| `--strict` | tolerated | **fails** |
| `--changed-only BASE` (CI) | **fails** | **fails** |

## Files touched

- `scripts/deploy/check_deploy_hygiene.py` — `AlembicFinding`, `scan_raw_alembic()`,
  allowlist, reporting and strict failure
- `platform_api/tests/test_deploy_hygiene_alembic.py` (new, 6 tests)

## Tests

- detects a chained `&& alembic upgrade head`, a bare shell line, and a `stamp`;
- ignores comments, docstrings and `grep` inspection lines;
- ignores the locked entrypoint;
- every current deploy script is either clean or allowlisted, so `--strict` does
  not regress.

`ruff` clean, `check_deploy_hygiene.py --strict` exits 0.

## Follow-ups

- Retire the 16 allowlisted scripts one at a time; the list should shrink, never
  grow.
- `camxora-sandbox-remote.sh` is allowlisted, not fixed — the sandbox install
  path should also use the locked entrypoint.
