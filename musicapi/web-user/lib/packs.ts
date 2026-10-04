/**
 * Presentation helpers for turning raw `credit_packs` rows into Suno-style value
 * framing — tier name, songs per pack, cost per song and volume bonus. All of it
 * is derived from the live packs (and the live `music` credit cost), so changing
 * a pack in the admin console updates every surface automatically. There is no
 * second price list to maintain.
 */

export interface RawPack {
  id: string;
  amount: number;
  price: number;
  currency: string;
}

export interface Plan extends RawPack {
  tier: string;
  songs: number;
  perSong: number;
  creditsPerUsd: number;
  bonusCredits: number;
  bonusPct: number;
  badge: string;
}

export interface PricingRow {
  endpoint: string;
  model: string | null;
  credit_cost: number;
}

/**
 * A `music` generation costs 10 credits and returns two songs
 * (live production/sandbox pricing, reconciled by
 * migrations/0025_credit_pack_production_parity.sql). Used only to translate
 * packs into "songs" for display; the live cost is read from GET /pricing
 * whenever it is reachable.
 */
export const DEFAULT_MUSIC_COST = 10;

/** Every `music` generation returns this many tracks. */
export const SONGS_PER_GENERATION = 2;

// Shown only until the live packs load (or if the API is unreachable) so the
// pricing section never renders empty. Values mirror the live production and
// sandbox credit-pack ladder ($10–$100).
export const FALLBACK_PACKS: RawPack[] = [
  { id: "fallback-1", amount: 2500, price: 10, currency: "USD" },
  { id: "fallback-2", amount: 10000, price: 30, currency: "USD" },
  { id: "fallback-3", amount: 20000, price: 60, currency: "USD" },
  { id: "fallback-4", amount: 33000, price: 100, currency: "USD" },
];

const TIER_NAMES = ["Starter", "Creator", "Pro", "Studio"];

/** Credits-per-song cost from the pricing rows, or null when not published. */
export function musicCostFromPricing(pricing?: PricingRow[]): number | null {
  const music = pricing?.find((p) => p.endpoint === "music" && p.model === null);
  return music && music.credit_cost > 0 ? music.credit_cost : null;
}

export function usd(n: number): string {
  return `$${n.toFixed(n < 1 ? 3 : 2)}`;
}

export function buildPlans(packs: RawPack[], musicCost: number = DEFAULT_MUSIC_COST): Plan[] {
  const sorted = [...packs].filter((p) => p.price > 0).sort((a, b) => a.amount - b.amount);
  const cost = musicCost > 0 ? musicCost : DEFAULT_MUSIC_COST;
  const baseRate = sorted.length ? sorted[0].amount / sorted[0].price : 0;
  const popularIdx = sorted.length >= 3 ? Math.floor((sorted.length - 1) / 2) : -1;

  // "Best value" is the pack with the most credits per $1 — not simply the
  // largest, because a non-monotonic ladder (e.g. the $100 pack being slightly
  // worse per credit than the $60 one) would otherwise be mislabelled. Ties go
  // to the larger pack.
  const rates = sorted.map((p) => p.amount / p.price);
  const maxRate = rates.length ? Math.max(...rates) : 0;
  let bestValueIdx = -1;
  rates.forEach((rate, i) => {
    if (
      Math.abs(rate - maxRate) < 1e-9 &&
      (bestValueIdx === -1 || sorted[i].amount > sorted[bestValueIdx].amount)
    ) {
      bestValueIdx = i;
    }
  });

  return sorted.map((p, i) => {
    const creditsPerUsd = p.amount / p.price;
    const songs = Math.floor(p.amount / cost) * SONGS_PER_GENERATION;
    const perSong = songs > 0 ? p.price / songs : 0;
    const bonusCredits = baseRate > 0 ? Math.max(0, Math.round(p.amount - baseRate * p.price)) : 0;
    const bonusPct = baseRate > 0 ? Math.max(0, (creditsPerUsd / baseRate - 1) * 100) : 0;
    const badge =
      i === bestValueIdx && sorted.length > 1
        ? "Best value"
        : i === popularIdx
          ? "Most popular"
          : "";
    return {
      ...p,
      tier: TIER_NAMES[i] ?? `Pack ${i + 1}`,
      songs,
      perSong,
      creditsPerUsd,
      bonusCredits,
      bonusPct,
      badge,
    };
  });
}
