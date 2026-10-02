import { AccountPool } from "./src/pool.js";
async function main() {
  const pool = await AccountPool.fromDb();
  console.log("pool size:", pool.clients.length);
  const client = (pool as any).clients[0] as any;
  console.log("client id:", client.id);
  try {
    const clipId = "0ceba9e7-d1df-4ff3-a675-de64522b6201";
    console.log("\n=== client.downloadBuffer(mp3) ===");
    const t1 = Date.now();
    const { buffer: b1, contentType: ct1 } = await client.downloadBuffer(clipId, "mp3");
    console.log("  bytes:", b1.length, "ct:", ct1, "ms:", Date.now() - t1);
    const h1 = Buffer.from(b1.buffer, b1.byteOffset, Math.min(16, b1.length));
    console.log("  head hex:", [...h1].map(x => x.toString(16).padStart(2,"0")).join(" "));
    console.log("  ascii:", [...h1].map(x => (x>=32&&x<=126)?String.fromCharCode(x):".").join(""));

    console.log("\n=== client.downloadBuffer(wav) ===");
    const t2 = Date.now();
    const { buffer: b2, contentType: ct2 } = await client.downloadBuffer(clipId, "wav");
    console.log("  bytes:", b2.length, "ct:", ct2, "ms:", Date.now() - t2);
    const h2 = Buffer.from(b2.buffer, b2.byteOffset, Math.min(16, b2.length));
    console.log("  head hex:", [...h2].map(x => x.toString(16).padStart(2,"0")).join(" "));
    console.log("  ascii:", [...h2].map(x => (x>=32&&x<=126)?String.fromCharCode(x):".").join(""));
  } catch (e: any) {
    console.error("ERR:", e?.stack ?? String(e));
  }
}
main();
