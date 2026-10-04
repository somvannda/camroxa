/**
 * captcha-live-test — proves the 2Captcha solve path end-to-end.
 *
 * Status-only by default. Add `--solve` to exercise the configured solver key
 * against Suno's Turnstile, or `--generate` for a real V6-Mini submission on a
 * routed (`prefer_free`) account. For a quick read-only per-account status,
 * see scripts/check-captcha.ts.
 *
 * Usage (from musicapi/):
 *   npx tsx scripts/captcha-live-test.ts            # status only — no spend
 *   npx tsx scripts/captcha-live-test.ts --solve    # solve one Turnstile (pays 2Captcha)
 *   npx tsx scripts/captcha-live-test.ts --generate # real V6-Mini generation (spends Suno credits)
 */

import "dotenv/config";
import { AccountPool } from "../src/pool.js";
import { loadRuntimeSettings } from "../src/runtimeSettings.js";
import { config } from "../src/config.js";
import { solveCaptchaForAccount } from "../src/captcha.js";
import { pool as dbPool } from "../src/db.js";

const flags = new Set(process.argv.slice(2));

async function main() {
  // Pick up a 2Captcha key saved in the admin console, not just .env.
  await loadRuntimeSettings();

  console.log("2Captcha key:", config.twoCaptchaKey ? `configured (len=${config.twoCaptchaKey.length})` : "NOT CONFIGURED");
  console.log("Turnstile sitekey:", config.turnstileSitekey);
  console.log("Turnstile pageurl:", config.turnstilePageUrl);

  const pool = await AccountPool.fromDb();
  console.log(`\nAccounts in pool: ${pool.size}`);

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
        .catch((e) => ({ credits: -1, models: [] as string[], err: e instanceof Error ? e.message : String(e) })),
      client.captchaRequired().catch(() => null),
    ]);
    const err = "err" in billing && billing.err ? ` ERR=${billing.err}` : "";
    console.log(
      `  - ${id} [${client.account.type ?? "free"}] credits=${billing.credits} captchaRequired=${captcha} models=[${billing.models.join(", ")}]${err}`,
    );
  }

  const chosen = await pool.pick("chirp-goose", "prefer_free");
  console.log(`\nRoute chirp-goose/prefer_free -> ${chosen.account.id} (${chosen.account.type ?? "free"})`);

  if (flags.has("--solve")) {
    console.log("\nSolving one Turnstile via 2Captcha (costs a few cents)…");
    const t0 = Date.now();
    const token = await solveCaptchaForAccount({ twoCaptchaKey: config.twoCaptchaKey });
    console.log(`  token len=${token.length} in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
    console.log("  SUCCESS: 2Captcha returned a token — key, balance, sitekey and pageurl are all valid.");
  }

  if (flags.has("--generate")) {
    console.log(`\nSubmitting a real V6-Mini generation on ${chosen.account.id} (spends Suno credits)…`);
    const clips = await chosen.generateMusic({
      model: "chirp-goose",
      gptDescriptionPrompt: "short lo-fi test loop about a rainy window",
      instrumental: true,
    });
    console.log(`  submitted ${clips.length} clip(s): ${clips.map((c) => c.id).join(", ")}`);
    console.log("  SUCCESS: Suno accepted the generation — captcha was solved and consumed.");
  }

  if (!flags.has("--solve") && !flags.has("--generate")) {
    console.log("\n(Status-only run. Add --solve or --generate to exercise the captcha path.)");
  }

  await dbPool.end();
}

main().catch(async (e) => {
  console.error("\nFAILED:", e instanceof Error ? e.message : e);
  await dbPool.end().catch(() => undefined);
  process.exit(1);
});
