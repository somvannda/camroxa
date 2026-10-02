import { writeFileSync } from "node:fs";

async function main() {
  const login = await fetch("http://127.0.0.1:3000/auth/login", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: "user@example.com", password: "user123" }),
  });
  const l: any = await login.json();
  console.log("login ok token len=", l.token?.length);

  const clip = "0ceba9e7-d1df-4ff3-a675-de64522b6201";

  // test 1: mp3
  const t0 = Date.now();
  const resp = await fetch(
    "http://127.0.0.1:3000/me/download?clip_id=" + clip + "&format=mp3",
    { headers: { authorization: "Bearer " + l.token } },
  );
  const t1 = Date.now();
  const buf = Buffer.from(await resp.arrayBuffer());
  const hex = buf.subarray(0, 16).toString("hex");
  console.log("--- TEST 1: MP3 ---");
  console.log(
    "HTTP=",
    resp.status,
    "ct=",
    resp.headers.get("content-type"),
    "cl=",
    resp.headers.get("content-length"),
  );
  console.log("bytes=", buf.length, "elapsed=", ((t1 - t0) / 1000).toFixed(1) + "s");
  console.log("head hex =", hex);
  console.log("head ascii =", buf.subarray(0, 4).toString("ascii"));
  const id3Ok = hex.startsWith("494433");
  console.log("ID3 check =", id3Ok ? "PASS ✓" : "FAIL (no ID3)");
  if (id3Ok) writeFileSync("e2e_mp3.mp3", buf);

  // test 2: wav same clip
  const tw0 = Date.now();
  const resp2 = await fetch(
    "http://127.0.0.1:3000/me/download?clip_id=" + clip + "&format=wav",
    { headers: { authorization: "Bearer " + l.token } },
  );
  const tw1 = Date.now();
  const buf2 = Buffer.from(await resp2.arrayBuffer());
  const hex2 = buf2.subarray(0, 16).toString("hex");
  console.log("");
  console.log("--- TEST 2: WAV ---");
  console.log(
    "HTTP=",
    resp2.status,
    "ct=",
    resp2.headers.get("content-type"),
    "cl=",
    resp2.headers.get("content-length"),
  );
  console.log("bytes=", buf2.length, "elapsed=", ((tw1 - tw0) / 1000).toFixed(1) + "s");
  console.log("head hex =", hex2);
  console.log(
    "head ascii =",
    buf2.subarray(0, 4).toString("ascii"),
    buf2.subarray(8, 12).toString("ascii"),
    buf2.subarray(12, 16).toString("ascii"),
  );
  const riffOk =
    hex2.startsWith("52494646") &&
    buf2.subarray(8, 12).toString("ascii") === "WAVE" &&
    buf2.subarray(12, 16).toString("ascii") === "fmt ";
  console.log("RIFF WAVE fmt check =", riffOk ? "PASS ✓" : "FAIL (no RIFF/WAVE)");
  if (riffOk) writeFileSync("e2e_wav.wav", buf2);

  console.log("");
  console.log("--- SIZE CHECK ---");
  const mp3Expected = 5_054_339;
  const wavExpected = 43_060_250;
  console.log(
    "Expected mp3 ~5MB (" + mp3Expected + "). Match =",
    Math.abs(buf.length - mp3Expected) < 100_000 ? "PASS ✓" : "DIFF mp3=" + buf.length,
  );
  console.log(
    "Expected wav ~43MB (" + wavExpected + "). Match =",
    Math.abs(buf2.length - wavExpected) < 500_000 ? "PASS ✓" : "DIFF wav=" + buf2.length,
  );
}
main().catch((e) => {
  console.error("FATAL", e);
  process.exit(1);
});
