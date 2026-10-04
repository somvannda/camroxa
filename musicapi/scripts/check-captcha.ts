/**
 * check-captcha — quick, read-only per-account captcha/health status.
 *
 * Never solves a captcha and never generates: safe to run against production.
 * For the full live probe (solve the Turnstile / submit a real generation) use
 * scripts/captcha-live-test.ts.
 *
 * Usage (from musicapi/):
 *   npx tsx scripts/check-captcha.ts
 */

import "dotenv/config";
import { AccountPool } from "../src/pool.js";
import { loadRuntimeSettings } from "../src/runtimeSettings.js";
import { config } from "../src/config.js";
import { pool as dbPool } from "../src/db.js";

async function main() {
  // Mirror the running server: merge admin-stored settings over .env so a key
  // saved in the dashboard is picked up here too.
  await loadRuntimeSettings();

  console.log("2Captcha key:", config.twoCaptchaKey ? "configured" : "NOT configured");
  console.log("Turnstile sitekey:", config.turnstileSitekey);

  const pool = await AccountPool.fromDb();
  console.log(`\nAccounts: ${pool.size}`);

  for (const id of pool.list()) {
    const client = pool.get(id);
    if (!client) continue;
    const [billing, captcha] = await Promise.all([
      client
        .billingInfo()
        .then((b) => ({
          credits: b.total_credits_left ?? 0,
          models: (b.models ?? []).filter((m) => m.can_use).map((m) => m.external_key).filter(Boolean),
        }))
        .catch(() => ({ credits: -1, models: [] as string[] })),
      client.captchaRequired().catch(() => null),
    ]);
    console.log(
      `  - ${id} [${client.account.type ?? "free"}] credits=${billing.credits} captchaRequired=${captcha} models=[${billing.models.join(", ")}]`,
    );
  }

  await dbPool.end();
}

main().catch(async (e) => {
  console.error("FAILED:", e instanceof Error ? e.message : e);
  await dbPool.end().catch(() => undefined);
  process.exit(1);
});
