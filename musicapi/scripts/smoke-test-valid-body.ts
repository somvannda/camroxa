const routes: Array<[string, string, string]> = [
  ["POST", "/v1/generate", '{"model":"chirp-auk","prompt":"happy upbeat lo-fi piano melody","make_instrumental":true}'],
  ["POST", "/v1/music/extend", '{"clip_id":"11111111-1111-1111-1111-111111111111","prompt":"more drums"}'],
  ["POST", "/v1/music/stems", '{"clip_id":"11111111-1111-1111-1111-111111111111"}'],
  ["POST", "/v1/music/mashup", '{"clip_ids":["11111111-1111-1111-1111-111111111111","22222222-2222-2222-2222-222222222222"]}'],
  ["POST", "/v1/music/wav", '{"clip_id":"11111111-1111-1111-1111-111111111111"}'],
  ["POST", "/v1/generate/upload-extend", '{"audio_url":"https://example.com/song.mp3","prompt":"continue with a guitar solo"}'],
  ["POST", "/v1/generate/upload-cover", '{"audio_url":"https://example.com/song.mp3","prompt":"acoustic cover"}'],
];

const base = process.env.BASE || "http://localhost:3003";
const API_KEY = "sk-test-123";

async function main() {
  for (const [method, path, body] of routes) {
    const opts: RequestInit = {
      method,
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${API_KEY}`,
      },
    };
    if (method !== "GET") opts.body = body;
    const t0 = Date.now();
    const res = await fetch(base + path, opts);
    const text = (await res.text()).slice(0, 320);
    console.log(`${method} ${path} -> ${res.status} (${Date.now()-t0}ms) ${text}`);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
