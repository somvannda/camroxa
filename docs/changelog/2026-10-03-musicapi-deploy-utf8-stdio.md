# musicapi sandbox/production deploy: survive Unicode build output on Windows

## Summary

`scripts/deploy/sync_musicapi_sandbox.py` (and the production twin, which imports
`deploy()` from it) could crash mid-deploy on a Windows console with
`UnicodeEncodeError: 'charmap' codec can't encode character ...` while streaming
remote build output. The remote `npm`/`tsc`/`next build` output contains Unicode
spinner frames and ANSI escapes; the default cp1252 stdout codec cannot encode
them, so the local client aborted even though the remote build was healthy.

## Technical impact

- `scripts/deploy/sync_musicapi_sandbox.py`: new `_force_utf8_stdio()` reconfigures
  `sys.stdout`/`sys.stderr` to UTF-8 with `errors="replace"`, called at the top of
  `deploy()`. This covers both the sandbox entrypoint and
  `deploy_musicapi_production.py`, which reuses the same `deploy()`.

## Files touched

- `scripts/deploy/sync_musicapi_sandbox.py`
- `docs/changelog/2026-10-03-musicapi-deploy-utf8-stdio.md`

## Tests

- `python -m py_compile scripts/deploy/sync_musicapi_sandbox.py` → clean.
- Reproduced in practice: a deploy aborted on `\u2819` before the fix; re-running
  with `PYTHONUTF8=1` completed, and this change makes that the default.
