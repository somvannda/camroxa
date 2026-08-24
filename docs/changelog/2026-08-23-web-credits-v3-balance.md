# 2026-08-23 — Web Credits number from v3

Sandbox only. Production not touched. Item 17 (one wallet) is still later.

Music web header, Create, and profile Credit Balance read `/api/v3/me/credits` first. CutLuy leftover from `/api/v1/v2/credits/balance` still adds into that one spendable number so paid web users do not see 0. `GET /api/v3/me/credits` now mints the Free daily grant so the chrome shows 50 after login.
