/**
 * Reclaim the eager-WAV objects that `ingestMedia()` used to write.
 *
 * Before this change landed, every generated clip stored an MP3, a WAV and the
 * m4a master. WAV was 82.9% of all `musicapi/` bytes on the live bucket while
 * being a *paid* download that most clips never had taken. Having stopped
 * writing them, the ones already stored still cost money forever, because
 * nothing in this codebase ever deletes an object.
 *
 * They are safe to expire: `ensureAudio()` (server.ts) rebuilds a WAV from the
 * `masters/` copy the first time someone actually buys the download.
 *
 * Scope is deliberately narrow:
 *   - only `musicapi/wav/` — NOT `masters/`, `clips/`, `images/` or `videos/`
 *   - NOT `web-music/`, which belongs to the legacy platform_api stack and
 *     holds paid protected-playback assets for live streams
 *
 * Usage:
 *   tsx scripts/b2-wav-lifecycle.ts                 # dry run: show what would change
 *   tsx scripts/b2-wav-lifecycle.ts --apply         # write the rule
 *   tsx scripts/b2-wav-lifecycle.ts --apply --days 30
 *   tsx scripts/b2-wav-lifecycle.ts --remove        # drop our rule (keeps others)
 *
 * Existing rules are preserved: this merges rather than replacing the config.
 */
import {
  S3Client,
  GetBucketLifecycleConfigurationCommand,
  PutBucketLifecycleConfigurationCommand,
  type LifecycleRule,
} from "@aws-sdk/client-s3";
import { config, storageConfigured } from "../src/config.js";

const RULE_ID = "musicapi-expire-eager-wav";

function parseArgs(argv: string[]) {
  const args = { apply: false, remove: false, days: 14 };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--apply") args.apply = true;
    else if (a === "--remove") args.remove = true;
    else if (a === "--days") {
      const n = Number(argv[++i]);
      if (!Number.isFinite(n) || n < 1 || n > 3650) {
        throw new Error(`--days must be 1..3650 (got ${argv[i]})`);
      }
      args.days = Math.floor(n);
    } else if (a === "--help" || a === "-h") {
      console.log("usage: tsx scripts/b2-wav-lifecycle.ts [--apply] [--remove] [--days N]");
      process.exit(0);
    } else {
      throw new Error(`unknown argument: ${a}`);
    }
  }
  if (args.apply && args.remove) throw new Error("--apply and --remove are mutually exclusive");
  return args;
}

async function readRules(client: S3Client, bucket: string): Promise<LifecycleRule[]> {
  try {
    const res = await client.send(new GetBucketLifecycleConfigurationCommand({ Bucket: bucket }));
    return res.Rules ?? [];
  } catch (e) {
    // B2 returns NoSuchLifecycleConfiguration when the bucket has no rules yet.
    if (e instanceof Error && e.name === "NoSuchLifecycleConfiguration") return [];
    throw e;
  }
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  if (!storageConfigured()) {
    throw new Error("Object storage is not configured (B2 endpoint/bucket/key missing).");
  }

  const client = new S3Client({
    endpoint: config.storage.endpoint,
    region: config.storage.region,
    credentials: { accessKeyId: config.storage.keyId, secretAccessKey: config.storage.applicationKey },
    forcePathStyle: true,
  });
  const bucket = config.storage.bucket;
  // Honour the configured key prefix so a non-default deployment expires the
  // right tree rather than a hard-coded one.
  const prefix = `${config.storage.prefix ? `${config.storage.prefix}/` : ""}wav/`;

  const existing = await readRules(client, bucket);
  const others = existing.filter((r) => r.ID !== RULE_ID);
  const current = existing.find((r) => r.ID === RULE_ID);

  console.log(`bucket        : ${bucket}`);
  console.log(`prefix        : ${prefix}`);
  console.log(`existing rules: ${existing.length}${others.length ? ` (${others.length} belonging to other owners, preserved)` : ""}`);
  console.log(`our rule      : ${current ? "present" : "absent"}`);
  console.log("");

  let next: LifecycleRule[] = others;
  if (args.remove) {
    if (!current) {
      console.log("Nothing to remove; our rule is not configured.");
      return;
    }
    next = others;
    console.log(`Would REMOVE rule "${RULE_ID}".`);
  } else {
    const rule: LifecycleRule = {
      ID: RULE_ID,
      Status: "Enabled",
      Filter: { Prefix: prefix },
      Expiration: { Days: args.days },
      // Incomplete multipart uploads are pure garbage and never billable-useful.
      AbortIncompleteMultipartUpload: { DaysAfterInitiation: 7 },
    };
    next = [...others, rule];
    console.log(`Would ensure rule "${RULE_ID}":`);
    console.log(`  expire objects under ${prefix} after ${args.days} day(s)`);
    console.log(`  abort incomplete multipart uploads after 7 day(s)`);
  }

  console.log("\nresulting rule set:");
  console.log(JSON.stringify(next, null, 2));

  if (!args.apply) {
    console.log("\nDRY RUN — nothing written. Re-run with --apply to persist.");
    return;
  }

  if (next.length === 0) {
    // PutBucketLifecycleConfiguration rejects an empty rule set.
    const { DeleteBucketLifecycleCommand } = await import("@aws-sdk/client-s3");
    await client.send(new DeleteBucketLifecycleCommand({ Bucket: bucket }));
    console.log("\nApplied: lifecycle configuration deleted (no rules remain).");
    return;
  }

  await client.send(
    new PutBucketLifecycleConfigurationCommand({
      Bucket: bucket,
      LifecycleConfiguration: { Rules: next },
    }),
  );
  console.log(`\nApplied: ${next.length} rule(s) written to ${bucket}.`);
}

main().catch((e) => {
  console.error("FAILED:", e instanceof Error ? e.message : e);
  process.exit(1);
});
