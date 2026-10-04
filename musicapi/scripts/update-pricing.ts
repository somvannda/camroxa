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

async function main() {
  const nineCredit = [
    "extend", "cover", "sounds", "stems", "remaster",
    "mashup", "add_vocals", "add_instrumental", "replace_section",
    "persona", "upload_extend", "upload_cover",
    "recovery_audio", "boost_style", "midi_generate",
    "voice_phrase", "voice_generate", "voice_apply", "voice_extend",
  ];
  for (const ep of nineCredit) await upsertPrice(ep, null, 9);
  await upsertPrice("music", null, 10);
  const oneCredit = [
    "upload_init", "upload_register", "voice_validate", "voice_record",
    "lyrics_detail", "stems_detail", "video_detail",
    "cover_detail", "subtitle_detail", "recovery_detail", "mp4_detail",
    "midi_detail", "timestamped_lyrics_detail",
  ];
  for (const ep of oneCredit) await upsertPrice(ep, null, 1);
  // WAV is download-only: the conversion routes only resolve a signed URL, and
  // the bytes are paid for by `wav_download` on GET /me/download.
  await upsertPrice("wav", null, 0);
  await upsertPrice("wav_detail", null, 0);
  await upsertPrice("mp3_download", null, 0);
  await upsertPrice("wav_download", null, 3);
  await upsertPrice("lyrics", null, 2);
  await upsertPrice("cover_image", null, 5);
  await upsertPrice("mp4_generate", null, 5);

  await pool.query("DELETE FROM credit_packs");
  await pool.query(
    "INSERT INTO credit_packs (amount, price, currency) VALUES (1000, 5, 'USD'), (2300, 10, 'USD'), (5500, 20, 'USD'), (8800, 30, 'USD')",
  );
  console.log(`Pricing upserted: ${nineCredit.length} endpoints @ 9 credits, music=10, ${oneCredit.length} @ 1 credit, lyrics=2, cover_image=5, mp4_generate=5, wav/wav_detail/mp3_download=0, wav_download=3. Packs $5/1k, $10/2.3k, $20/5.5k, $30/8.8k.`);
  await pool.end();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
