const TIER_CHANNEL_ANCHORS = [2, 6, 10] as const;
const PROFILE_ADDON_STEP = 2;
const SEMI_ANNUAL_MONTHS = 6;
const ANNUAL_MONTHS = 12;
const DEFAULT_SEMI_ANNUAL_DISCOUNT_PERCENT = 15;
const DEFAULT_ANNUAL_DISCOUNT_PERCENT = 25;

export type BillingTermQuote = {
  label: string;
  billingCycleDays: number;
  totalCents: number;
  monthlyEquivalentCents: number;
  discountPercent: number;
};

export type ProfileAddonQuote = {
  currentChannels: number;
  addonChannels: number;
  newTotalChannels: number;
  monthlyAddonCents: number;
};

export type ChannelPricingOptions = {
  semiAnnualDiscountPercent?: number;
  annualDiscountPercent?: number;
};

export function roundWholeDollars(cents: number): number {
  if (cents <= 0) return 0;
  return Math.ceil(cents / 100) * 100;
}

export function linearPlanMonthlyCents(blockCents: number, channelCount: number): number {
  const pairs = Math.max(0, Math.floor(channelCount / PROFILE_ADDON_STEP));
  return pairs * blockCents;
}

export function tierMonthlyPriceCents(
  baseMonthlyCents: number,
  _baseChannels: number,
  targetChannels: number,
): number {
  return linearPlanMonthlyCents(baseMonthlyCents, targetChannels);
}

export function buildTierMonthlyPrices(baseMonthlyCents: number, _baseChannels = 2): Record<number, number> {
  return Object.fromEntries(
    TIER_CHANNEL_ANCHORS.map((channels) => [
      channels,
      linearPlanMonthlyCents(baseMonthlyCents, channels),
    ]),
  ) as Record<number, number>;
}

export function interpolateTierPrice(channelCount: number, tierPrices: Record<number, number>): number {
  if (channelCount <= 0) return 0;
  const sortedAnchors = Object.keys(tierPrices)
    .map(Number)
    .sort((a, b) => a - b);
  const firstAnchor = sortedAnchors[0];
  const blockCents =
    tierPrices[2] ?? (firstAnchor !== undefined ? tierPrices[firstAnchor] : undefined);
  if (blockCents == null) return 0;
  return roundWholeDollars(blockCents * (channelCount / PROFILE_ADDON_STEP));
}

export function quoteProfileAddonMonthly(
  currentChannels: number,
  addonPriceCents: number,
  addonChannels = PROFILE_ADDON_STEP,
): ProfileAddonQuote {
  return {
    currentChannels,
    addonChannels,
    newTotalChannels: currentChannels + addonChannels,
    monthlyAddonCents: roundWholeDollars(addonPriceCents),
  };
}

export function billingTermQuotes(
  monthlyCents: number,
  options: ChannelPricingOptions = {},
): BillingTermQuote[] {
  if (monthlyCents <= 0) return [];

  const semiDiscountPercent = options.semiAnnualDiscountPercent ?? DEFAULT_SEMI_ANNUAL_DISCOUNT_PERCENT;
  const annualDiscountPercent = options.annualDiscountPercent ?? DEFAULT_ANNUAL_DISCOUNT_PERCENT;
  const monthly = roundWholeDollars(monthlyCents);
  const semiTotal = roundWholeDollars(Math.round(monthly * SEMI_ANNUAL_MONTHS * (1 - semiDiscountPercent / 100)));
  const annualTotal = roundWholeDollars(Math.round(monthly * ANNUAL_MONTHS * (1 - annualDiscountPercent / 100)));

  return [
    {
      label: 'Monthly',
      billingCycleDays: 30,
      totalCents: monthly,
      monthlyEquivalentCents: monthly,
      discountPercent: 0,
    },
    {
      label: `6 Months (${semiDiscountPercent}% OFF)`,
      billingCycleDays: 180,
      totalCents: semiTotal,
      monthlyEquivalentCents: roundWholeDollars(Math.round(semiTotal / SEMI_ANNUAL_MONTHS)),
      discountPercent: semiDiscountPercent,
    },
    {
      label: `Annual (${annualDiscountPercent}% OFF)`,
      billingCycleDays: 365,
      totalCents: annualTotal,
      monthlyEquivalentCents: roundWholeDollars(Math.round(annualTotal / ANNUAL_MONTHS)),
      discountPercent: annualDiscountPercent,
    },
  ];
}

export function combinedBillingTermQuotes(
  planMonthlyCents: number,
  addonMonthlyCents = 0,
  options: ChannelPricingOptions = {},
): BillingTermQuote[] {
  return billingTermQuotes(roundWholeDollars(planMonthlyCents + addonMonthlyCents), options);
}

export function scaleQuotaValue(value: number | null, fromChannels: number, toChannels: number): number | null {
  if (value == null) return null;
  if (fromChannels <= 0 || toChannels <= 0) return value;
  return Math.max(0, Math.round(value * (toChannels / fromChannels)));
}

export function formatUsd(cents: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(cents / 100);
}

export function formatChannelPlanName(channels: number, billingCycleDays: number): string {
  if (billingCycleDays === 180) return `6 Months · ${channels}-channel`;
  if (billingCycleDays === 365) return `Annual · ${channels}-channel`;
  return `Monthly · ${channels}-channel`;
}
