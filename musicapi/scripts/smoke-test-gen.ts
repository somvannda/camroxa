const base = process.env.BASE || "http://localhost:3003";
const API_KEY = "sk-test-123";

async function main() {
  // Test v1/music valid body → should return 202 + job_id
  const res = await fetch(base + "/v1/music", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${API_KEY}`,
    },
    body: JSON.stringify({
      model: "chirp-auk",
      prompt: "short test: gentle lullaby, piano",
      make_instrumental: true,
      wait_audio: false,
    }),
  });
  const txt = await res.text();
  console.log("POST /v1/music ->", res.status, txt.slice(0, 200));

  // If 202, poll task once
  if (res.status === 202) {
    const j = JSON.parse(txt);
    await new Promise((r) => setTimeout(r, 3000));
    const t = await fetch(base + "/v1/task/" + j.job_id, {
      headers: { authorization: `Bearer ${API_KEY}` },
    });
    console.log("GET /v1/task/" + j.job_id + " ->", t.status, (await t.text()).slice(0, 500));
  }

  // Test sounds endpoint
  const s = await fetch(base + "/v1/sounds", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${API_KEY}`,
    },
    body: JSON.stringify({ prompt: "rain on window", make_instrumental: true }),
  });
  console.log("POST /v1/sounds ->", s.status, (await s.text()).slice(0, 200));
}

main().catch(console.error);
