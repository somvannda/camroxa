import "dotenv/config";
import { AccountPool } from "../src/pool.js";

async function probe(client: import("../src/client.js").SunoClient, path: string, init: RequestInit = {}): Promise<void> {
  const res = await client.rawRequest(path, init);
  const text = await res.text();
  console.log(`\n=== ${init.method ?? "GET"} ${path} === status=${res.status}`);
  try {
    console.log(JSON.stringify(JSON.parse(text), null, 2).slice(0, 1200));
  } catch {
    console.log(text.slice(0, 1200));
  }
}

async function main(): Promise<void> {
  console.log("Round 8: /api/clip/upload exists (405) - probing all methods + variants");
  const pool = await AccountPool.fromDb();
  const client = await pool.pick(undefined, "paid_only");
  console.log("using account:", client.account.id);

  // /api/clip/upload - all HTTP verbs
  for (const method of ["GET", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]) {
    await probe(client, "/api/clip/upload", { method });
  }

  // Nearby clip upload patterns
  for (const p of [
    "/api/clip/upload/policy",
    "/api/clip/upload/audio",
    "/api/clip/audio-upload",
    "/api/clip/audio_upload",
    "/api/clip/create-upload",
    "/api/clip/upload/init",
    "/api/clip/upload/s3",
  ]) {
    await probe(client, p, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ extension: "mp3" }) });
  }

  process.exit(0);
}

main().catch((e) => {
  console.error("PROBE ERROR:", e);
  process.exit(1);
});
