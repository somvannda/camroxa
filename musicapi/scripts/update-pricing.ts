import "dotenv/config";
import { pool } from "../src/db.js";

async function upsertPrice(endpoint: string, model: string | null, creditCost: number): Promise<void> {
  const exists = await pool.query(
    "SELECT id FROM pricing WHERE endpoint = $1 AND (model IS NOT DISTINCT FROM $2)",
    [endpoint, model],
  );
  if (exists.rows.length) {
    await pool.query("UPDATE pricing SET credit_cost = $1 WHERE id = $2", [
      creditCost,
      exists.rows[0].id as string,
    ]);
  } else {
    await pool.query(
      "INSERT INTO pricing (endpoint, model, credit_cost) VALUES ($1, $2, $3)",
      [endpoint, model, creditCost],
    );
  }
}

// Production pricing (admin.musicapi.camxora.com/admin/pricing) is the source of
// truth. Keep this list in lockstep with it.
const PRICING: Array<[string, number]> = [
  ["music", 10],
  ["lyrics", 0],
  ["extend", 10],
  ["cover", 10],
  ["sounds", 3],
  ["stems", 8],
  ["stems_split", 20],
  ["stems_advanced", 12],
  ["remaster", 10],
  ["mashup", 10],
  ["add_vocals", 10],
  ["add_instrumental", 10],
  ["replace_section", 9],
  ["cover_image", 0],
  ["persona", 0],
  ["wav", 0],
  ["mp3_download", 0],
  ["wav_download", 0],
  ["upload_extend", 10],
  ["upload_cover", 10],
  ["upload_init", 1],
  ["upload_register", 1],
  ["recovery_audio", 10],
  ["mp4_generate", 2],
  ["boost_style", 0],
  ["midi_generate", 3],
  ["voice_phrase", 1],
  ["voice_validate", 1],
  ["voice_record", 1],
  ["voice_generate", 10],
  ["voice_apply", 10],
  ["voice_extend", 10],
  ["lyrics_detail", 0],
  ["wav_detail", 0],
  ["stems_detail", 0],
  ["video_detail", 0],
  ["cover_detail", 0],
  ["subtitle_detail", 0],
  ["recovery_detail", 0],
  ["mp4_detail", 0],
  ["midi_detail", 0],
  ["timestamped_lyrics_detail", 0],
];

// Four-tier volume ladder.
const PACKS: Array<[amount: number, price: number]> = [
  [1000, 5],
  [2300, 10],
  [5500, 20],
  [8800, 30],
];

async function main() {
  for (const [endpoint, cost] of PRICING) {
    await upsertPrice(endpoint, null, cost);
  }

  await pool.query("DELETE FROM credit_packs");
  await pool.query(
    "INSERT INTO credit_packs (amount, price, currency) VALUES (1000, 5, 'USD'), (2300, 10, 'USD'), (5500, 20, 'USD'), (8800, 30, 'USD')",
  );

  const packsSummary = PACKS.map(([amount, price]) => `$${price}/${amount.toLocaleString()}`).join(", ");
  console.log(`Pricing upserted: ${PRICING.length} endpoints at production values. Packs: ${packsSummary}.`);
  await pool.end();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
