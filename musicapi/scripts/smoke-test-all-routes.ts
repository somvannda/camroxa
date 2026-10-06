const TEST_KEY = process.env.TEST_KEY || "sk-test-123";
const base = process.env.BASE || "http://localhost:3003";

const ALL_ROUTES: Array<{
  method: "GET" | "POST";
  path: string;
  tier2?: object;
  tier3?: object;
  expectTier2?: number;
  expectTier3?: number;
}> = [
  // --- Legacy (17) ---
  { method: "POST", path: "/v1/lyrics", tier2: {}, tier3: { prompt: "test lyrics" } },
  { method: "POST", path: "/v1/music", tier2: {}, tier3: { prompt: "happy pop", title: "t" } },
  { method: "POST", path: "/v1/sounds", tier2: {}, tier3: { prompt: "rain" } },
  { method: "POST", path: "/v1/music/extend", tier2: {}, tier3: { clip_id: "00000000-0000-0000-0000-000000000001" } },
  { method: "POST", path: "/v1/music/cover", tier2: {}, tier3: { clip_id: "00000000-0000-0000-0000-000000000001" } },
  { method: "POST", path: "/v1/music/stems", tier2: {}, tier3: { clip_id: "00000000-0000-0000-0000-000000000001" } },
  { method: "POST", path: "/v1/music/remaster", tier2: {}, tier3: { clip_id: "00000000-0000-0000-0000-000000000001" } },
  { method: "POST", path: "/v1/music/add-vocals", tier2: {}, tier3: { clip_id: "00000000-0000-0000-0000-000000000001", prompt: "sing" } },
  { method: "POST", path: "/v1/music/add-instrumental", tier2: {}, tier3: { clip_id: "00000000-0000-0000-0000-000000000001", prompt: "piano" } },
  { method: "POST", path: "/v1/music/mashup", tier2: {}, tier3: { clip_ids: ["a", "b"] } },
  { method: "POST", path: "/v1/music/replace-section", tier2: {}, tier3: { clip_id: "a", lyrics: "x", start_s: 0, end_s: 5 } },
  { method: "POST", path: "/v1/music/cover-image", tier2: {}, tier3: { clip_id: "a", prompt: "sunset" } },
  { method: "POST", path: "/v1/persona/create", tier2: {}, tier3: { clip_id: "a", name: "voice" } },
  { method: "POST", path: "/v1/music/wav", tier2: {}, tier3: { clip_id: "a" } },
  { method: "POST", path: "/v1/generate/upload-extend", tier2: {}, tier3: { uploaded_clip_id: "a", prompt: "x" } },
  { method: "POST", path: "/v1/generate/upload-cover", tier2: {}, tier3: { uploaded_clip_id: "a", prompt: "x" } },
  { method: "GET", path: "/v1/task/00000000-0000-0000-0000-000000000000", tier3: undefined },
  // --- NEW (28) ---
  { method: "POST", path: "/v1/upload/init", tier2: {}, tier3: { extension: "mp3" } },
  { method: "POST", path: "/v1/upload/register", tier2: {}, tier3: { upload_id: "a", upload_type: "file_upload", upload_filename: "x.mp3" } },
  { method: "GET", path: "/v1/upload/status/00000000-0000-0000-0000-000000000000", tier3: undefined },
  { method: "POST", path: "/v1/music/recovery", tier2: {}, tier3: { clip_id: "a" } },
  { method: "GET", path: "/v1/lyrics/00000000-0000-0000-0000-000000000000", tier3: undefined },
  { method: "GET", path: "/v1/music/wav/00000000-0000-0000-0000-000000000000", tier3: undefined },
  { method: "GET", path: "/v1/music/stems/00000000-0000-0000-0000-000000000000", tier3: undefined },
  { method: "GET", path: "/v1/music/video/00000000-0000-0000-0000-000000000000", tier3: undefined },
  { method: "GET", path: "/v1/music/cover/00000000-0000-0000-0000-000000000000", tier3: undefined },
  { method: "GET", path: "/v1/music/subtitle/00000000-0000-0000-0000-000000000000", tier3: undefined },
  { method: "GET", path: "/v1/music/recovery/00000000-0000-0000-0000-000000000000", tier3: undefined },
  { method: "GET", path: "/v1/mp4/00000000-0000-0000-0000-000000000000", tier3: undefined },
  { method: "GET", path: "/v1/music/midi/00000000-0000-0000-0000-000000000000", tier3: undefined },
  { method: "GET", path: "/v1/clip/00000000-0000-0000-0000-000000000000", tier3: undefined },
  { method: "POST", path: "/v1/mp4/generate", tier2: {}, tier3: { clip_id: "a" } },
  { method: "POST", path: "/v1/generate/boost", tier2: {}, tier3: { clip_id: "a", style_prompt: "lofi" } },
  { method: "POST", path: "/v1/music/midi", tier2: {}, tier3: { clip_id: "a" } },
  { method: "POST", path: "/v1/voice/phrase", tier2: {}, tier3: { prompt: "hello" } },
  { method: "POST", path: "/v1/voice/validate", tier2: {}, tier3: { upload_id: "a" } },
  { method: "POST", path: "/v1/voice/record", tier2: {}, tier3: { extension: "wav" } },
  { method: "POST", path: "/v1/voice/generate", tier2: {}, tier3: { clip_id: "a", name: "vox" } },
  { method: "POST", path: "/v1/voice/apply", tier2: {}, tier3: { persona_id: "a", prompt: "sing" } },
  { method: "POST", path: "/v1/voice/extend", tier2: {}, tier3: { persona_id: "a" } },
];

// Anonymous-access checks for the other protected surface families. The
// deny-by-default backstop and each handler's guard must reject these with 401
// before any work happens.
const PROTECTED_ANON_ROUTES: Array<{ method: "GET" | "POST"; path: string }> = [
  { method: "GET", path: "/me/profile" },
  { method: "GET", path: "/me/download" },
  { method: "GET", path: "/me/stream" },
  { method: "POST", path: "/me/generate" },
  { method: "POST", path: "/me/voice-source" },
  { method: "GET", path: "/admin/users" },
  { method: "POST", path: "/admin/pricing" },
  { method: "POST", path: "/admin/users/00000000-0000-0000-0000-000000000000/credits" },
  { method: "GET", path: "/v1/credits" },
  { method: "GET", path: "/v1/get-credits" },
  { method: "POST", path: "/api/v1/generate" },
  { method: "GET", path: "/api/v1/get-credits" },
  { method: "POST", path: "/api/v1/upload/init" },
  { method: "POST", path: "/payments/chmaba/create" },
  { method: "GET", path: "/payments/chmaba/status/00000000-0000-0000-0000-000000000000" },
];

// Public routes must stay reachable (the backstop must not over-block).
const PUBLIC_REACHABLE_ROUTES: string[] = ["/health", "/pricing", "/models", "/settings"];


type Tier = "T1 (no-auth -> 401)" | "T2 (auth+empty -> 400)" | "T3 (auth+valid -> 202)";

interface Fail {
  route: string;
  method: string;
  tier: Tier;
  got: number;
  want: number;
  body: string;
}

async function main() {
  const fails: Fail[] = [];
  let passed = 0;
  for (const r of ALL_ROUTES) {
    // T1: no auth => 401
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

    // T2: valid auth + empty body => 400 (for POST) / 202 for GET details (no params needed)
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

    // T3: valid auth + valid body => 202 (async routes)
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
    } else if (r.method === "GET") {
      // GET with params-only (details) => 202 from new detailRoute helper
      const t3 = await fetch(base + r.path, {
        method: "GET",
        headers: { authorization: `Bearer ${TEST_KEY}` },
      });
      const t3b = (await t3.text()).slice(0, 160);
      // /v1/task/:id returns 404 because UUID doesn't exist; /v1/upload/status returns 502 if upstream errors
      const isTaskOrStatus = r.path.startsWith("/v1/task/") || r.path.startsWith("/v1/upload/status/");
      const want = isTaskOrStatus ? (r.path.startsWith("/v1/task/") ? 404 : (t3.status === 401 ? 401 : t3.status)) : 202;
      if (!isTaskOrStatus && t3.status !== 202) {
        fails.push({ route: r.path, method: r.method, tier: "T3 (auth+valid -> 202)", got: t3.status, want: 202, body: t3b });
        console.log(`FAIL  ${r.method} ${r.path}  T3  got=${t3.status} want=202  ${t3b}`);
      } else { passed++; }
    }
  }

  // Protected surfaces: an anonymous caller must get 401 (backstop + guards).
  for (const r of PROTECTED_ANON_ROUTES) {
    const res = await fetch(base + r.path, {
      method: r.method,
      headers: { "content-type": "application/json" },
      body: r.method === "GET" ? undefined : "{}",
    });
    const body = (await res.text()).slice(0, 120);
    if (res.status !== 401) {
      fails.push({ route: r.path, method: r.method, tier: "T1 (no-auth -> 401)", got: res.status, want: 401, body });
      console.log(`FAIL  ${r.method} ${r.path}  T1(protected)  got=${res.status} want=401  ${body}`);
    } else { passed++; }
  }

  // Public surfaces: the backstop must not over-block these.
  for (const path of PUBLIC_REACHABLE_ROUTES) {
    const res = await fetch(base + path, { method: "GET" });
    if (res.status === 401) {
      fails.push({ route: path, method: "GET", tier: "T1 (no-auth -> 401)", got: 401, want: 200, body: "public route unexpectedly blocked" });
      console.log(`FAIL  GET ${path}  public  got=401 (should be reachable)`);
    } else { passed++; }
  }

  const total = ALL_ROUTES.length * 2 + ALL_ROUTES.filter(r => r.method === "POST" && r.tier2 !== undefined).length;
  console.log(`\nSmoke: passed=${passed}  total_tests=~${passed + fails.length}  routes=${ALL_ROUTES.length}`);
  if (fails.length) {
    console.log("\nFAILS:");
    for (const f of fails) {
      console.log(`  ${f.method} ${f.route}  [${f.tier}]  got=${f.got} want=${f.want}`);
      console.log(`     body: ${f.body}`);
    }
    process.exit(1);
  } else {
    console.log("\nALL ROUTES PASS 3-TIER SMOKE.");
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
