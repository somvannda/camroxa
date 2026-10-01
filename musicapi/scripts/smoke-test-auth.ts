const routes: Array<[string, string, string]> = [
  ["POST", "/v1/music/extend", '{}'],
  ["POST", "/v1/music/cover", '{}'],
  ["POST", "/v1/music/stems", '{}'],
  ["POST", "/v1/music/remaster", '{}'],
  ["POST", "/v1/music/add-vocals", '{}'],
  ["POST", "/v1/music/add-instrumental", '{}'],
  ["POST", "/v1/music/mashup", '{}'],
  ["POST", "/v1/music/replace-section", '{}'],
  ["POST", "/v1/music/cover-image", '{}'],
  ["POST", "/v1/persona/create", '{}'],
  ["POST", "/v1/music/wav", '{}'],
  ["POST", "/v1/generate/upload-extend", '{}'],
  ["POST", "/v1/generate/upload-cover", '{}'],
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
    const res = await fetch(base + path, opts);
    const text = (await res.text()).slice(0, 260);
    console.log(`${method} ${path} -> ${res.status}  ${text}`);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
