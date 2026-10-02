/**
 * smoke-test-sunoapi-contract — asserts our registered routes cover sunoapi.org's
 * public API surface, so any client written against api.sunoapi.org is drop-in.
 *
 * Pure and offline: boots the server in-process (no DB, no network, no credits)
 * and checks Fastify's `hasRoute()` for every documented path.
 *
 *   npx tsx scripts/smoke-test-sunoapi-contract.ts
 *
 * Exits non-zero if any expected route is missing.
 */
import "dotenv/config";
import { buildServer } from "../src/server.js";

/** sunoapi.org's published OpenAPI paths (docs.sunoapi.org). */
const EXPECTED: Array<[string, string]> = [
  // Music / generation
  ["POST", "/api/v1/generate"],
  ["POST", "/api/v1/generate/extend"],
  ["POST", "/api/v1/generate/upload-cover"],
  ["POST", "/api/v1/generate/upload-extend"],
  ["POST", "/api/v1/generate/add-instrumental"],
  ["POST", "/api/v1/generate/add-vocals"],
  ["GET", "/api/v1/generate/record-info"],
  ["GET", "/api/v1/generate/credit"],
  ["POST", "/api/v1/generate/get-timestamped-lyrics"],
  ["POST", "/api/v1/style/generate"],
  ["POST", "/api/v1/lyrics"],
  ["GET", "/api/v1/lyrics/record-info"],
  ["POST", "/api/v1/wav/generate"],
  ["GET", "/api/v1/wav/record-info"],
  ["POST", "/api/v1/vocal-removal/generate"],
  ["GET", "/api/v1/vocal-removal/record-info"],
  ["POST", "/api/v1/midi/generate"],
  ["GET", "/api/v1/midi/record-info"],
  ["POST", "/api/v1/mp4/generate"],
  ["GET", "/api/v1/mp4/record-info"],
  ["POST", "/api/v1/generate/mashup"],
  ["POST", "/api/v1/generate/replace-section"],
  ["POST", "/api/v1/suno/cover/generate"],
  ["POST", "/api/v1/generate/generate-persona"],
  ["GET", "/api/v1/suno/cover/record-info"],
  ["POST", "/api/v1/generate/sounds"],
  ["POST", "/api/v1/suno/recovery"],
  ["GET", "/api/v1/suno/recovery/record-info"],
  // Voice
  ["POST", "/api/v1/voice/validate"],
  ["GET", "/api/v1/voice/validate-info"],
  ["POST", "/api/v1/voice/generate"],
  ["GET", "/api/v1/voice/record-info"],
  ["POST", "/api/v1/voice/regenerate"],
  ["POST", "/api/v1/voice/check-voice"],
  // File Upload API
  ["POST", "/api/file-base64-upload"],
  ["POST", "/api/file-stream-upload"],
  ["POST", "/api/file-url-upload"],
];

const app = await buildServer({ pool: {} as never });

let missing = 0;
for (const [method, url] of EXPECTED) {
  const ok = app.hasRoute({ method: method as never, url });
  if (!ok) {
    missing += 1;
    console.log(`MISSING  ${method} ${url}`);
  }
}
console.log(
  `\n${EXPECTED.length - missing}/${EXPECTED.length} sunoapi.org paths present` +
    (missing ? ` — ${missing} MISSING` : " — OK"),
);

await app.close().catch(() => {});
process.exit(missing ? 1 : 0);
