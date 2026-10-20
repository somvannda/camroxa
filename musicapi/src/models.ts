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
  // v6 family — current Suno default. Verified live: V6 -> chirp-hawk,
  // V6-WILD -> chirp-hawk-wild, V6-MINI -> chirp-goose (all usable).
  v6: "chirp-hawk",
  "chirp-v6": "chirp-hawk",
  "v6-wild": "chirp-hawk-wild",
  "chirp-v6-wild": "chirp-hawk-wild",
  "v6-mini": "chirp-goose",
  "chirp-v6-mini": "chirp-goose",
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

/**
 * Default account-routing policy for a model when no `routing_rules` row
 * overrides it.
 *
 * `chirp-goose` (V6-Mini) is the free-tier model, so it runs on free accounts
 * first — falling back to a paid account only when none is available. Every
 * other model is premium and must use a paid account. The model is normalised
 * first so retired keys that fold onto chirp-goose (`v6-mini`, `v3-5`, …) route
 * the same as the canonical key. Pure so it can be unit-tested without a pool.
 */
export function defaultRoutingPolicy(
  model?: string | null,
): "prefer_free" | "paid_only" {
  return normalizeModel(model) === "chirp-goose" ? "prefer_free" : "paid_only";
}

/** Admin-editable monthly free-allowance settings (see `freeMonthly` in config.ts). */
export interface AllowanceConfig {
  enabled: boolean;
  model: string;
}

/**
 * Whether a *music* request may spend the monthly free allowance: enabled, an
 * explicit model, and the normalised model matches the configured free model.
 * Sounds and every derivative stay on purchased credits. A request with no
 * model is never eligible — Suno's default is a premium model, so omitting the
 * field must not unlock the allowance.
 */
export function isAllowanceModel(
  model: string | null | undefined,
  tier: AllowanceConfig,
): boolean {
  if (!tier.enabled || !model) return false;
  const want = normalizeModel(tier.model);
  return Boolean(want) && normalizeModel(model) === want;
}

/**
 * Whether the monthly allowance may pay for this model. The configured free
 * model is always eligible. After a credit-pack purchase the remaining
 * allowance becomes universal (`universal` true), so it can also pay for V6 /
 * V6-WILD. Pure for unit tests.
 */
export function canSpendAllowance(
  model: string | null | undefined,
  tier: AllowanceConfig,
  universal = false,
): boolean {
  if (!tier.enabled || !model) return false;
  return isAllowanceModel(model, tier) || universal;
}

/** Human label for a model key, used in user-facing credit/upsell messages. */
const MODEL_LABELS: Record<string, string> = {
  "chirp-hawk": "V6",
  "chirp-hawk-wild": "V6-WILD",
  "chirp-goose": "V6-Mini",
};

export function modelLabel(model?: string | null): string | null {
  if (!model) return null;
  const key = normalizeModel(model);
  return (key && MODEL_LABELS[key]) ?? model;
}

/**
 * Routing policy for V6-Mini, independent of who pays (monthly allowance or
 * purchased credits): free Suno accounts first, and by default *only* free
 * accounts. `allowPaidFallback` is the admin safety valve for a dead free pool.
 * Pure for unit tests.
 */
export function freeModelRoutingPolicy(
  allowPaidFallback: boolean,
): "free_only" | "prefer_free" {
  return allowPaidFallback ? "prefer_free" : "free_only";
}
