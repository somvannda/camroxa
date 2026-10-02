const routes: Array<[string, string]> = [
  ["POST", "/v1/music/extend"],
  ["POST", "/v1/music/cover"],
  ["POST", "/v1/music/stems"],
  ["POST", "/v1/music/remaster"],
  ["POST", "/v1/music/add-vocals"],
  ["POST", "/v1/music/add-instrumental"],
  ["POST", "/v1/music/mashup"],
  ["POST", "/v1/music/replace-section"],
  ["POST", "/v1/music/cover-image"],
  ["POST", "/v1/persona/create"],
  ["POST", "/v1/music/wav"],
  ["POST", "/v1/generate/upload-extend"],
  ["POST", "/v1/generate/upload-cover"],
  ["GET", "/v1/task/00000000-0000-0000-0000-000000000000"],
];

const base = process.env.BASE || "http://localhost:3003";

async function main() {
  for (const [method, path] of routes) {
    const opts: RequestInit = { method, headers: { "content-type": "application/json" } };
    if (method !== "GET") opts.body = "{}";
    const res = await fetch(base + path, opts);
    const text = (await res.text()).slice(0, 200);
    console.log(`${method} ${path} -> ${res.status}  ${text}`);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
