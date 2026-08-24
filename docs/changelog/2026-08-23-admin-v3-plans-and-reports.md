# 2026-08-23 — Admin Plans cleanup + v3 reports

Sandbox only. Production not touched.

Matches `docs/credits-only-plan-unification.md` §8. Generate flag stays **On**. Item 17 (one wallet) is still later.

## Plans

`/plans` is the one credits-only catalog. Rows are grouped Public / Hidden active / Inactive. Copy no longer says Generate is still on v1 quotas. The live-path toggle is labeled as the sandbox v3 test (leave On).

## Reports

- Usage and Finance treat `v3_music` / `v3_lyric` / grants as the same operations as desktop.
- Finance **Grant issued** reads `v3_period_grant` + `v3_daily_grant` instead of a hardcoded dash.
- Settings → Music Web no longer edits the deleted free-daily setting. Free daily credits are the Free plan row on `/plans`.

CutLuy checkout still writes `web_subscriptions`. Do not treat this as the later one-wallet project.
