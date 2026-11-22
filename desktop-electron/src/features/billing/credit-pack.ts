/** Shared shape for a published credit pack. */
export interface CreditPack {
  id: string;
  slug: string;
  name: string;
  description: string;
  total_credits: number;
  price_cents: number;
  display_order: number;
  songs_equivalent: number;
}

export function formatMoney(cents: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(cents / 100);
}

/** Extra value vs the first/base pack, as a percentage. */
export function extraValue(pack: CreditPack, base: CreditPack | undefined): string {
  if (!base || base.price_cents <= 0 || pack.price_cents <= 0) return "Base";
  const baseRate = base.total_credits / base.price_cents;
  const packRate = pack.total_credits / pack.price_cents;
  const percent = Math.round((packRate / baseRate - 1) * 100);
  return percent <= 0 ? "Base" : `+${percent}%`;
}

/** The production "Most popular" pack, with a name fallback for older APIs. */
export function isPopularPack(pack: CreditPack): boolean {
  return pack.slug === "medium" || /medium/i.test(pack.name);
}
