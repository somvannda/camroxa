import "dotenv/config";
import { AccountPool } from "../src/pool.js";

async function probe(client: import("../src/client.js").SunoClient, path: string, init: RequestInit = {}): Promise<void> {
  const res = await client.rawRequest(path, init);
  const text = await res.text();
  console.log(`\n=== ${init.method ?? "GET"} ${path} === status=${res.status}`);
  try {
    console.log(JSON.stringify(JSON.parse(text), null, 2).slice(0, 1500));
  } catch {
    console.log(text.slice(0, 1500));
  }
}

async function main(): Promise<void> {
  console.log("Probing Suno API via paid account (round 7 - upload_extend schema + upload policy)...");
  const pool = await AccountPool.fromDb();
  const client = await pool.pick(undefined, "paid_only");
  console.log("using account:", client.account.id);
  const uid = "550e8400-e29b-41d4-a716-446655440000";

  // 1. Confirm /api/download/authorize UNWRAPPED body works
  await probe(client, "/api/download/authorize", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ item_id: uid, item_type: "clip", format: "mp3" }),
  });

  // 2. Check upload_extend task (figure out required fields)
  await probe(client, "/api/generate/v2-web/", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      task: "upload_extend",
      generation_type: "TEXT",
      mv: "chirp-crow",
    }),
  });

  // 3. cover_infill task (cover with uploaded file ref)
  await probe(client, "/api/generate/v2-web/", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      task: "cover_infill",
      generation_type: "TEXT",
      mv: "chirp-crow",
    }),
  });

  // 4. Try policy endpoint candidates
  const paths = [
    "/api/audio/upload/policy",
    "/api/audio_upload",
    "/api/v2/upload",
    "/api/files/upload",
    "/api/uploads/create",
    "/api/clip/upload",
    "/api/user_upload",
    "/api/user-upload/create",
    "/api/project/upload/audio",
    "/api/s3/policy",
    "/api/storage/policy",
  ];
  for (const p of paths) {
    await probe(client, p, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ extension: "mp3" }),
    });
  }

  process.exit(0);
}

main().catch((e) => {
  console.error("PROBE ERROR:", e);
  process.exit(1);
});
