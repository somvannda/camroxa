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

// Mirror the live production/sandbox pricing snapshot (see
// migrations/0026_pricing_production_alignment.sql), so a manual
// `update-pricing` run can never re-introduce local-only prices.
const PRICING: Array<[string, number]> = [
  ["music", 10],
  ["extend", 10],
  ["cover", 10],
  ["mashup", 10],
  ["add_vocals", 10],
  ["add_instrumental", 10],
  ["remaster", 10],
  ["recovery_audio", 10],
  ["upload_extend", 10],
  ["upload_cover", 10],
  ["voice_generate", 10],
  ["voice_apply", 10],
  ["voice_extend", 10],
  ["replace_section", 9],
  ["stems", 8],
  ["stems_advanced", 12],
  ["stems_split", 20],
  ["sounds", 3],
  ["midi_generate", 3],
  ["mp4_generate", 2],
  ["upload_init", 1],
  ["upload_register", 1],
  ["voice_phrase", 1],
  ["voice_validate", 1],
  ["voice_record", 1],
  ["boost_style", 0],
  ["lyrics", 0],
  ["lyrics_detail", 0],
  ["cover_detail", 0],
  ["cover_image", 0],
  ["persona", 0],
  ["midi_detail", 0],
  ["mp3_download", 0],
  ["mp4_detail", 0],
  ["recovery_detail", 0],
  ["stems_detail", 0],
  ["subtitle_detail", 0],
  ["timestamped_lyrics_detail", 0],
  ["video_detail", 0],
  ["wav", 0],
  ["wav_detail", 0],
  ["wav_download", 0],
];

async function main() {
  for (const [endpoint, creditCost] of PRICING) await upsertPrice(endpoint, null, creditCost);

  // `credit_packs` has no unique key, so it is rebuilt wholesale. Historical
  // transactions keep their pack_id via ON DELETE SET NULL.
  await pool.query("DELETE FROM credit_packs");
  await pool.query(
    "INSERT INTO credit_packs (amount, price, currency) VALUES (1000, 5, 'USD'), (2300, 10, 'USD'), (5500, 20, 'USD'), (8800, 30, 'USD')",
  );
  console.log(
    `Pricing upserted: ${PRICING.length} endpoints to the production snapshot (music=10). Packs $5/1k, $10/2.3k, $20/5.5k, $30/8.8k.`,
  );
  await pool.end();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
