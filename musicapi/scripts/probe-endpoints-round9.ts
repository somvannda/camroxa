import "dotenv/config";
import { AccountPool } from "../src/pool.js";
import { pool as dbPool } from "../src/db.js";

async function probe(client: import("../src/client.js").SunoClient, method: string, path: string, body?: unknown): Promise<{ status: number; text: string }> {
  const init: RequestInit = { method };
  if (body !== undefined) {
    init.headers = { "content-type": "application/json" };
    init.body = JSON.stringify(body);
  }
  const res = await client.rawRequest(path, init);
  return { status: res.status, text: await res.text() };
}

function summarize(label: string, method: string, path: string, status: number, bodyIn: unknown, text: string) {
  if (status === 404) return;
  const body = bodyIn !== undefined ? JSON.stringify(bodyIn).slice(0, 80) : "";
  console.log(`${label.padEnd(4)} ${method.padEnd(5)} ${path.padEnd(60)} ${String(status).padEnd(4)} BODY:${body.padEnd(80)} RESP:${text.slice(0, 260)}`);
}

async function main(): Promise<void> {
  console.log("Round 9 Probes — paid account. Searching for video/mp4, voice, midi, recovery, boost, clip-op endpoints\n");
  const pool = await AccountPool.fromDb();
  const client = await pool.pick("chirp-fenix", "paid_only");
  console.log("Using account:", client.account.id, "type:", client.account.type, "\n");
  const fakeId = "550e8400-e29b-41d4-a716-446655440000";

  // 1. Upload flow endpoints (GET) — confirmed exists from browser capture: /api/uploads/audio/
  console.log("=== Upload flow (confirmed via browser capture) ===");
  for (const [method, path, body] of [
    ["GET", "/api/uploads/audio/", undefined],
    ["GET", `/api/uploads/audio/${fakeId}/`, undefined],
    ["GET", `/api/uploads/audio/${fakeId}/upload-finish/`, undefined],
    ["POST", "/api/uploads/audio/", { extension: "mp3", upload_type: "file_upload" }],
    ["POST", `/api/uploads/audio/${fakeId}/upload-finish/`, { id: fakeId }],
  ] as const) {
    const r = await probe(client, method, path, body);
    summarize("UP", method, path, r.status, body, r.text);
  }

  // 2. /api/clip/{id}/... operations
  console.log("\n=== /api/clip/{id}/... operations ===");
  const clipOps = [
    "vox-stem", "lyrics", "subtitles", "subtitle", "wav", "mp4", "video", "midi",
    "download", "recovery", "recovery-audio", "recovery_audio", "boost", "boost-style",
    "style-boost", "stems", "split", "cover", "image", "details", "detail", "info",
    "remix", "persona", "upsample", "remaster", "separate", "vocals", "instrumental",
  ];
  for (const op of clipOps) {
    for (const method of ["GET", "POST"] as const) {
      const r = await probe(client, method, `/api/clip/${fakeId}/${op}`, method === "POST" ? {} : undefined);
      summarize("CLIP", method, `/api/clip/{id}/${op}`, r.status, method === "POST" ? "{}" : "", r.text);
    }
  }

  // 3. Top-level endpoints (video_gen, mp4, midi, persona, vox, recovery, boost)
  console.log("\n=== Top-level: video/mp4/voice/midi/... ===");
  const topPaths: Array<[string, string, unknown]> = [
    ["POST", "/api/video_gen/mp4/generate", { clip_id: fakeId, quantity: 1 }],
    ["POST", "/api/video_gen/mp4", { clip_id: fakeId }],
    ["POST", "/api/mp4/generate", { clip_id: fakeId }],
    ["GET", `/api/mp4/${fakeId}`, undefined],
    ["POST", "/api/midi/generate", { clip_id: fakeId }],
    ["GET", `/api/midi/${fakeId}`, undefined],
    ["GET", "/api/persona/list", undefined],
    ["GET", "/api/personas", undefined],
    ["POST", "/api/recovery/generate", { clip_id: fakeId }],
    ["POST", "/api/recovery/audio", { clip_id: fakeId }],
    ["POST", "/api/generate/boost", { clip_id: fakeId, prompt: "more bass" }],
    ["POST", "/api/boost/generate", { clip_id: fakeId }],
    ["POST", "/api/vox/generate", { clip_id: fakeId, prompt: "test" }],
    ["POST", "/api/voice/generate", { clip_id: fakeId }],
    ["POST", "/api/vox/phrase", { prompt: "test" }],
    ["POST", "/api/voice/validate", { url: "test" }],
    ["POST", "/api/vox/record", {}],
    ["POST", "/api/vox/apply", { clip_id: fakeId, persona_id: "1" }],
    ["POST", "/api/voice/apply", { clip_id: fakeId, persona_id: "1" }],
    ["GET", `/api/download/clip/${fakeId}`, undefined],
    ["GET", `/api/download/mp4/${fakeId}`, undefined],
    ["GET", `/api/download/midi/${fakeId}`, undefined],
    ["GET", `/api/download/subtitle/${fakeId}`, undefined],
    ["GET", `/api/download/lyrics/${fakeId}`, undefined],
  ];
  for (const [method, path, body] of topPaths) {
    const r = await probe(client, method, path, body);
    summarize("TOP", method, path, r.status, body, r.text);
  }

  // 4. v2-web task enum for new tasks
  console.log("\n=== v2-web task enum ===");
  const candidateTasks = [
    "video_gen", "mp4_gen", "video", "mp4", "midi_gen", "midi", "generate_midi",
    "recovery_audio", "recovery", "boost", "style_boost", "boost_style", "vox_gen", "voice_gen",
    "timestamped_lyrics", "lyrics_timestamped", "video_thumbnail", "subtitle_gen",
    "generate_stems", "generate_lyrics", "lyric_gen", "vocals_gen", "vocal_gen",
    "inpainting", "outpainting", "gen_midi", "gen_mp4", "gen_video",
    "gen_recovery", "gen_boost", "voice_record", "voice_phrase",
    "srt", "captions", "video_motion", "animate",
  ];
  for (const task of candidateTasks) {
    const r = await probe(client, "POST", "/api/generate/v2-web/", {
      task,
      mv: "chirp-fenix",
      generation_type: "TEXT",
    });
    if (r.status !== 404) summarize("V2", "POST", `task:"${task}"`, r.status, `{task:${task}}`, r.text);
  }

  await dbPool.end();
}

main().catch((e) => { console.error(e); process.exit(1); });
