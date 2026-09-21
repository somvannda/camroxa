import { writeFileSync, readFileSync, mkdirSync } from "node:fs";

async function main() {
  const BASE = "http://127.0.0.1:3000";
  const login = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: "user@example.com", password: "user123" }),
  });
  const lj = await login.json();
  console.log("login:", login.status, "token_len:", lj.token.length);

  const CLIP_MP3 = "0ceba9e7-d1df-4ff3-a675-de64522b6201";
  const CLIP_WAV = "0ceba9e7-d1df-4ff3-a675-de64522b6201";
  const auth = { authorization: `Bearer ${lj.token}` };

  async function test(label: string, urlPath: string, outPath: string) {
    const t1 = Date.now();
    const r = await fetch(`${BASE}${urlPath}`, { headers: auth });
    const t2 = Date.now();
    const arr = new Uint8Array(await r.arrayBuffer());
    writeFileSync(outPath, arr);
    const head = arr.slice(0, 16);
    const hex = [...head].map((x) => x.toString(16).padStart(2, "0")).join(" ");
    const asc = [...head].map((x) => (x >= 32 && x <= 126 ? String.fromCharCode(x) : ".")).join("");
    console.log(
      `${label}: HTTP=${r.status} ct=${r.headers.get("content-type") ?? ""} cl=${r.headers.get("content-length") ?? ""} cd=${r.headers.get("content-disposition") ?? ""
      } bytes=${arr.length} ms=${t2 - t1}`,
    );
    console.log(`  hex: ${hex}`);
    console.log(`  asc: ${asc}`);
    return arr;
  }

  await test(
    "MP3 /me/download",
    `/me/download?clip_id=${CLIP_MP3}&format=mp3&force_download=1`,
    "node_mp3.mp3",
  );

  await test(
    "WAV /me/download",
    `/me/download?clip_id=${CLIP_WAV}&format=wav&force_download=1`,
    "node_wav.wav",
  );
}

main().catch((e) => {
  console.error("FATAL:", e);
  process.exit(1);
});
