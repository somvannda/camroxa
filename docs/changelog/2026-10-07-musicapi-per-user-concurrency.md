# musicapi: surface Suno concurrency caps through the deploy env

## Summary

Production ran with the built-in per-user concurrent-job cap of **2**
(`SUNO_MAX_CONCURRENT_PER_USER` default, `src/config.ts`). With a 5-account
pool the global ceiling is `5 × 4 = 20`, but the `ConcurrencyGate`
(`src/concurrency.ts`) admits at most 2 jobs for any single owner, and all of a
user's API keys share that owner budget. One busy user therefore showed
`running: 2` with the rest waiting, even though the pool could take far more.

The deploy installer (`scripts/deploy/camxora-musicapi-remote.sh`) rewrites
`musicapi/.env` wholesale on every run and never emitted the `SUNO_*` tuning
vars, so the cap could not be raised through the normal sandbox-first deploy
path — only by hand-editing the server's `.env`, which the next deploy would
wipe.

## Product impact

- Operators can now raise the per-user concurrent-job cap (e.g. 8) through the
  deploy secrets, so a single customer can use more of the pool instead of
  being pinned to 2.
- No behaviour change when the new secrets are left unset: the installer emits
  the same defaults the code already applied (per-account 4, global
  `pool.size × 4`, per-user 2, max-queue 1000).

## Technical impact

- `scripts/deploy/camxora-musicapi-remote.sh` — the `.env` heredoc now emits
  `SUNO_CONCURRENT_PER_ACCOUNT`, `SUNO_MAX_CONCURRENT`,
  `SUNO_MAX_CONCURRENT_PER_USER`, `SUNO_MAX_CONCURRENT_PER_ACCOUNT` and
  `SUNO_MAX_QUEUE`, each overridable via a `MUSICAPI_SUNO_*` secret. The numeric
  caps carry explicit defaults because an **empty** `.env` value is parsed as 0
  by `Number()` and would silently clamp a cap to 1; `SUNO_MAX_CONCURRENT` is
  emitted empty on purpose (`src/config.ts` treats a falsy value as "derive from
  the pool").
- `.deploy/secrets.production.env.example` / `.deploy/secrets.env.example` —
  documented the new `MUSICAPI_SUNO_*` secrets.
- `.deploy/secrets.production.env` (gitignored) — set
  `MUSICAPI_SUNO_MAX_CONCURRENT_PER_USER=8` for production. Sandbox keeps the
  default 2.

## Migration / deploy

1. Deploy `musicapi` through the normal sandbox-first chain; production with the
   driver's explicit `--yes`.
2. After the production deploy, confirm on
   `admin.musicapi.camxora.com/admin/system` that the **Suno concurrency** card
   shows `per user: 8` and that `running` can exceed 2 under a backlog.
3. No DB migration; no restart-order dependency.

## Tests

- Not yet run against the live hosts (change is the deploy-side plumbing + a
  secrets value). Verify with a short burst after the sandbox deploy, then the
  production card check above.

## Follow-ups

- Consider `MUSICAPI_QUEUE_DRIVER=redis` for restart durability (does **not**
  raise the concurrency limit by itself — the `ConcurrencyGate` still applies).
- Watch the global ceiling (20) and per-account cap (4) once the per-user cap is
  raised; add pool accounts before raising `SUNO_MAX_CONCURRENT`.
