import "dotenv/config";
import { AccountPool } from "../src/pool.js";
import { putObject, objectKey, objectExists } from "../src/storage.js";

/**
 * Backfill missing clips into object storage so playback streams instantly.
 *
 *   CLIPS="id1,id2" npx tsx scripts/backfill-clips.ts
 *
 * For each clip id it downloads the MP3 from Suno (3-step) and stores it under
 * `musicapi/clips/<id>.mp3` if not already present. Best-effort per clip.
 */
const ids = (process.env.CLIPS ?? "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);
if (ids.length === 0) {
  console.error("Set CLIPS to one or more comma-separated clip ids.");
  process.exit(1);
}

const pool = await AccountPool.fromDb();
if (pool.size === 0) {
  console.error("No Suno accounts in the pool.");
  process.exit(1);
}

let stored = 0;
for (const id of ids) {
  const key = objectKey("clips", `${id}.mp3`);
  if (await objectExists(key)) {
    console.log(`${id}: already stored`);
    continue;
  }
  try {
    const client = await pool.pick();
    const { buffer, contentType } = await client.downloadBuffer(id, "mp3");
    await putObject(key, buffer, contentType || "audio/mpeg");
    stored += 1;
    console.log(`${id}: stored ${buffer.length} bytes`);
  } catch (e) {
    console.error(`${id}: failed —`, e instanceof Error ? e.message : e);
  }
}
console.log(`done: ${stored}/${ids.length} stored`);
