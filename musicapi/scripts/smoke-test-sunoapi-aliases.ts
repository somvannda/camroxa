const TEST_KEY = process.env.TEST_KEY || "sk-test-123";
const base = process.env.BASE || "http://localhost:3003";

const P = "/api/v1";

const SUNOAPI_ALIASES: Array<{
  method: "GET" | "POST";
  path: string;
  tier2?: object;
  tier3?: object;
  expectTier2?: number;
  expectTier3?: number;
}> = [
  // --- Utility aliases (already existed) ---
  { method: "GET",  path: `${P}/get-credits` },
  { method: "GET",  path: `${P}/generate/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "POST", path: `${P}/generate`,            tier2: {}, tier3: { prompt: "test", customMode: false, model: "V4" } },
  { method: "POST", path: `${P}/generate`,            tier2: {}, tier3: { prompt: "adv params test", title: "T", style: "classical", customMode: true, styleWeight: 0.65, weirdnessConstraint: 0.7, audioWeight: 0.5, duration: 60, vocalGender: "f", negativeTags: "drums" } },
  { method: "POST", path: `${P}/lyrics`,              tier2: {}, tier3: { prompt: "test" } },
  { method: "POST", path: `${P}/generate/extend`,     tier2: {}, tier3: { audioId: "a" } },
  { method: "POST", path: `${P}/vocal-removal/generate`, tier2: {}, tier3: { audioId: "a" } },

  // --- NEW record-info detail aliases (per-category) ---
  { method: "GET",  path: `${P}/cover-suno/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "GET",  path: `${P}/cover/record-info?taskId=00000000-0000-0000-0000-000000000000`,      expectTier3: 404 },
  { method: "GET",  path: `${P}/extend-upload/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "GET",  path: `${P}/add-vocals/record-info?taskId=00000000-0000-0000-0000-000000000000`,  expectTier3: 404 },
  { method: "GET",  path: `${P}/add-instrumental/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "GET",  path: `${P}/music-remaster/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "GET",  path: `${P}/convert-to-wav/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "GET",  path: `${P}/vocal-removal/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "GET",  path: `${P}/create-music-video/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "GET",  path: `${P}/lyrics/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "GET",  path: `${P}/generate-persona/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "GET",  path: `${P}/generate/upload-cover/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "GET",  path: `${P}/generate/upload-extend/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "GET",  path: `${P}/generate/add-vocals/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "GET",  path: `${P}/generate/add-instrumental/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "GET",  path: `${P}/generate/boost/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "GET",  path: `${P}/generate/mashup/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "GET",  path: `${P}/generate/midi/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "GET",  path: `${P}/generate/cover/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "GET",  path: `${P}/generate/cover-image/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "GET",  path: `${P}/generate/recovery/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },
  { method: "GET",  path: `${P}/voice/record-info?taskId=00000000-0000-0000-0000-000000000000`, expectTier3: 404 },

  // --- NEW canonical /generate/* sub-path POST aliases ---
  { method: "POST", path: `${P}/generate/upload-cover`,     tier2: {}, tier3: { audioUrl: "https://example.com/x.mp3", prompt: "lofi" } },
  { method: "POST", path: `${P}/generate/upload-extend`,    tier2: {}, tier3: { audioUrl: "https://example.com/x.mp3", prompt: "extend" } },
  { method: "POST", path: `${P}/generate/add-vocals`,       tier2: {}, tier3: { audioId: "a", prompt: "sing" } },
  { method: "POST", path: `${P}/generate/add-instrumental`, tier2: {}, tier3: { audioId: "a", prompt: "piano" } },
  { method: "POST", path: `${P}/generate/generate-persona`, tier2: {}, tier3: { audioId: "00000000-0000-0000-0000-000000000000", name: "Smokey", vocalStart: 10, vocalEnd: 30, description: "tenor" } },
  { method: "POST", path: `${P}/generate/cover`,            tier2: {}, tier3: { audioId: "a" } },
  { method: "POST", path: `${P}/generate/cover-image`,      tier2: {}, tier3: { audioId: "a", prompt: "album art, sunset" } },
  { method: "POST", path: `${P}/generate/convert-wav`,      tier2: {}, tier3: { audioId: "a" } },
  { method: "POST", path: `${P}/generate/boost`,            tier2: {}, tier3: { audioId: "a", prompt: "warm analog studio" } },
  { method: "POST", path: `${P}/generate/music-video`,      tier2: {}, tier3: { audioId: "a", style: "anime" } },
  { method: "POST", path: `${P}/generate/mashup`,           tier2: { clip_ids: ["one"] }, tier3: { clip_ids: ["11111111-1111-1111-1111-111111111111","22222222-2222-2222-2222-222222222222"], prompt: "mashup" }, expectTier2: 400 },
  { method: "POST", path: `${P}/generate/midi`,             tier2: {}, tier3: { audioId: "a" } },
  { method: "POST", path: `${P}/generate/recovery`,         tier2: {}, tier3: { audioId: "a" } },

  // --- Voice aliases ---
  { method: "POST", path: `${P}/voice/phrase`,              tier2: {}, tier3: { prompt: "hello there" } },
  { method: "POST", path: `${P}/voice/validate`,            tier2: {}, tier3: { audioUrl: "https://example.com/x.mp3" } },
  { method: "POST", path: `${P}/voice/record`,              tier2: {}, tier3: { extension: "wav" } },
  { method: "POST", path: `${P}/voice/generate`,            tier2: { audioId: "a" }, tier3: { audioId: "00000000-0000-0000-0000-000000000000", name: "Test Voice", vocalStartS: 5, vocalEndS: 25 }, expectTier2: 400 },
  { method: "POST", path: `${P}/voice/apply`,               tier2: {}, tier3: { clipId: "a", prompt: "some lyrics", title: "T", tags: "pop" } },
  { method: "POST", path: `${P}/voice/extend`,              tier2: {}, tier3: { clipId: "a", prompt: "more song", continueAt: 60 } },

  // --- Upload 3-step + timestamped lyrics GET ---
  { method: "POST", path: `${P}/upload/init`,               tier2: {}, tier3: { extension: "mp3" } },
  { method: "POST", path: `${P}/upload/register`,           tier2: { upload_id: "x" }, tier3: { upload_id: "x", upload_type: "file_upload", upload_filename: "x.mp3" }, expectTier2: 400 },
  { method: "GET",  path: `${P}/upload/status/placeholder-upload-id`, expectTier3: 502 },
  { method: "GET",  path: `${P}/lyrics/some-clip-id` },

  // --- Legacy alternate-shape POST aliases ---
  { method: "POST", path: `${P}/cover-suno/generate`,       tier2: {}, tier3: { audioId: "a" } },
  { method: "POST", path: `${P}/cover/generate`,            tier2: {}, tier3: { audioId: "a" } },
  { method: "POST", path: `${P}/extend-upload`,             tier2: {}, tier3: { audioId: "a" } },
  { method: "POST", path: `${P}/add-vocals/generate`,       tier2: {}, tier3: { audioId: "a", prompt: "sing" } },
  { method: "POST", path: `${P}/add-instrumental/generate`, tier2: {}, tier3: { audioId: "a", prompt: "piano" } },
  { method: "POST", path: `${P}/music-remaster/generate`,   tier2: {}, tier3: { audioId: "a" } },
  { method: "POST", path: `${P}/convert-to-wav/generate`,   tier2: {}, tier3: { audioId: "a" } },
  { method: "POST", path: `${P}/create-music-video/generate`, tier2: {}, tier3: { audioId: "a" } },
  { method: "POST", path: `${P}/lyrics/generate`,           tier2: {}, tier3: { prompt: "hello" } },
];

type Tier = "T1 (no-auth -> 401)" | "T2 (auth+empty -> 400)" | "T3 (auth+valid -> 202)";

interface Fail {
  route: string; method: string; tier: Tier; got: number; want: number; body: string;
}

async function main() {
  const fails: Fail[] = [];
  let passed = 0;

  for (const r of SUNOAPI_ALIASES) {
    // T1: no auth -> 401
    const t1 = await fetch(base + r.path, {
      method: r.method,
      headers: { "content-type": "application/json" },
      body: r.method === "GET" ? undefined : "{}",
    });
    const t1b = (await t1.text()).slice(0, 120);
    if (t1.status !== 401) {
      fails.push({ route: r.path, method: r.method, tier: "T1 (no-auth -> 401)", got: t1.status, want: 401, body: t1b });
      console.log(`FAIL  ${r.method} ${r.path}  T1  got=${t1.status} want=401  ${t1b}`);
    } else { passed++; }

    // T2: auth + empty -> 400 (POSTs only)
    if (r.method === "POST" && r.tier2 !== undefined) {
      const t2 = await fetch(base + r.path, {
        method: "POST",
        headers: { "content-type": "application/json", authorization: `Bearer ${TEST_KEY}` },
        body: JSON.stringify(r.tier2),
      });
      const t2b = (await t2.text()).slice(0, 120);
      const want = r.expectTier2 ?? 400;
      if (t2.status !== want) {
        fails.push({ route: r.path, method: r.method, tier: "T2 (auth+empty -> 400)", got: t2.status, want, body: t2b });
        console.log(`FAIL  ${r.method} ${r.path}  T2  got=${t2.status} want=${want}  ${t2b}`);
      } else { passed++; }
    }

    // T3: auth + valid -> 202 (POSTs and record-info GETs)
    if (r.tier3 !== undefined) {
      const body = r.method === "GET" ? undefined : JSON.stringify(r.tier3);
      const t3 = await fetch(base + r.path, {
        method: r.method,
        headers: { "content-type": "application/json", authorization: `Bearer ${TEST_KEY}` },
        body,
      });
      const t3b = (await t3.text()).slice(0, 160);
      const want = r.expectTier3 ?? 202;
      if (t3.status !== want) {
        fails.push({ route: r.path, method: r.method, tier: "T3 (auth+valid -> 202)", got: t3.status, want, body: t3b });
        console.log(`FAIL  ${r.method} ${r.path}  T3  got=${t3.status} want=${want}  ${t3b}`);
      } else { passed++; }
    }
  }

  const total = SUNOAPI_ALIASES.length * 2 + SUNOAPI_ALIASES.filter(r => r.method === "POST").length;
  console.log(`\nSunoAPI /api/v1 aliases: passed=${passed}  total_tests=~${passed + fails.length}  routes=${SUNOAPI_ALIASES.length}`);
  if (fails.length) {
    console.log("\nFAILS:");
    for (const f of fails) {
      console.log(`  ${f.method} ${f.route}  [${f.tier}]  got=${f.got} want=${f.want}`);
      console.log(`     body: ${f.body}`);
    }
    process.exit(1);
  } else {
    console.log("\nALL SUNOAPI /api/v1/* ALIASES PASS 3-TIER SMOKE.");
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
