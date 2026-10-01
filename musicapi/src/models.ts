/**
 * Suno model-key normalisation.
 *
 * Suno retired the v3–v5.5 model keys but treats them inconsistently, verified
 * live against the API:
 *
 *   - `chirp-v4`, `chirp-v4-5`, `chirp-v4-5-all`, `chirp-v3-5`, `chirp-v3-5-b`
 *     are still accepted and silently remapped to the v6 family (the clips come
 *     back reporting `chirp-hawk` / `chirp-goose`).
 *   - `chirp-v5`, `chirp-v5-5` and the snake_case aliases Suno used to document
 *     (`V5_5`, `V5`, `V4_5ALL`) are hard-rejected with HTTP 400
 *     `{"error_type":"invalid_input","message":"The selected model isn't valid."}`.
 *
 * Callers that still send a retired key therefore either get a mystery 400 or a
 * track that reports a different model than they asked for. Mapping the retired
 * keys onto their current equivalent up front keeps old clients working and
 * makes the `jobs`/`usage_logs` record match what Suno actually renders.
 */

/** Retired key (lowercased, `_` folded to `-`) → the current Suno model. */
const MODEL_ALIASES: Record<string, string> = {
  // v5 / v5.5 — newer than v4.x, so they land on the current default (v6).
  "chirp-v5-5": "chirp-hawk",
  "v5-5": "chirp-hawk",
  "chirp-v5": "chirp-hawk",
  "v5": "chirp-hawk",
  // v4 family — remapped by Suno to chirp-hawk.
  "chirp-v4-5-all": "chirp-hawk",
  "chirp-v4-5all": "chirp-hawk",
  "v4-5all": "chirp-hawk",
  "chirp-v4-5": "chirp-hawk",
  "v4-5": "chirp-hawk",
  "chirp-v4": "chirp-hawk",
  "v4": "chirp-hawk",
  // v3.5 — remapped by Suno to the mini model.
  "chirp-v3-5-b": "chirp-goose",
  "v3-5-b": "chirp-goose",
  "chirp-v3-5": "chirp-goose",
  "v3-5": "chirp-goose",
  "chirp-v3": "chirp-goose",
  "v3": "chirp-goose",
};

/**
 * Map a requested model key onto a model Suno currently accepts. Unknown keys
 * (including every current model) are returned untouched, so a new Suno model
 * never needs a code change to keep working.
 */
export function normalizeModel(model?: string | null): string | undefined {
  if (!model) return undefined;
  const key = model.trim();
  if (!key) return undefined;
  return MODEL_ALIASES[key.toLowerCase().replace(/_/g, "-")] ?? key;
}
