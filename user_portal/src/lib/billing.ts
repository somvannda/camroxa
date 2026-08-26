"use client";

import { platformJson } from "@/lib/auth-fetch";

export type PublicPlanOffer = {
  id: string;
  promo_price_cents: number;
  max_redemptions: number;
  current_redemptions: number;
  remaining_redemptions: number;
  is_active: boolean;
};

export type PublicPlan = {
  id: string;
  name: string;
  price_cents: number;
  effective_price_cents: number;
  billing_cycle_days: number | null;
  profile_allowance: number;
  /** Suno packages (1 request = Primary + Secondary channel = 2 tracks). */
  monthly_song_limit: number | null;
  monthly_image_limit: number | null;
  /** Lyric + title + album pool. */
  monthly_draft_limit: number | null;
  daily_song_limit_per_channel: number;
  daily_image_limit_per_channel: number;
  daily_draft_limit_per_channel: number;
  monthly_video_limit?: number | null;
  monthly_merge_limit?: number | null;
  daily_video_limit?: number;
  daily_merge_limit?: number;
  included_wallet_credits?: number;
  monthly_credits?: number;
  daily_credits?: number;
  pricing_features?: string[];
  pricing_credit_lines?: string[];
  credits_per_generate?: number;
  offer: PublicPlanOffer | null;
};

export type BillingPayment = {
  id: string;
  provider: string;
  external_payment_id: string;
  plan_id: string;
  plan_name: string;
  amount_cents: number;
  currency: string;
  status: string;
  checkout_url: string;
  approved_at: string | null;
  fulfilled_at: string | null;
  original_amount_cents?: number | null;
  redeem_code?: string | null;
  product_type?: string;
  addon_channels?: number | null;
  created_at: string;
  updated_at: string;
};

export type BillingProvider = {
  id: string;
  label: string;
  kind: string;
  description: string;
  enabled: boolean;
  active: boolean;
  available: boolean;
};

export type BillingProviderConfig = {
  active_provider: string | null;
  paid_checkout_available: boolean;
  providers: BillingProvider[];
};

export type PlanTermDiscounts = {
  semi_annual_discount_percent: number;
  annual_discount_percent: number;
};

export async function listPublicPlans(): Promise<PublicPlan[]> {
  return platformJson<PublicPlan[]>({
    path: "/plans/public",
    method: "GET",
    auth: false,
  });
}

export async function getPublicPlanTermDiscounts(): Promise<PlanTermDiscounts> {
  return platformJson<PlanTermDiscounts>({
    path: "/plans/public/term-discounts",
    method: "GET",
    auth: false,
  });
}

export async function listBillingProviders(): Promise<BillingProviderConfig> {
  return platformJson<BillingProviderConfig>({
    path: "/billing/providers",
    method: "GET",
    auth: false,
  });
}

export async function createBillingPayment(
  planId: string,
  redeemCode?: string | null,
): Promise<BillingPayment> {
  return platformJson<BillingPayment>({
    path: "/billing/payments",
    method: "POST",
    body: {
      plan_id: planId,
      redeem_code: redeemCode?.trim() ? redeemCode.trim().toUpperCase() : null,
    },
  });
}

export async function getBillingPayment(paymentId: string): Promise<BillingPayment> {
  return platformJson<BillingPayment>({
    path: `/billing/payments/${encodeURIComponent(paymentId)}`,
    method: "GET",
  });
}

export async function resolveBillingPaymentByExternalId(
  externalPaymentId: string,
): Promise<BillingPayment> {
  return platformJson<BillingPayment>({
    path: `/billing/payments/resolve?external_payment_id=${encodeURIComponent(externalPaymentId)}`,
    method: "GET",
  });
}

export async function listMyBillingPayments(limit = 8): Promise<BillingPayment[]> {
  return platformJson<BillingPayment[]>({
    path: `/billing/payments?limit=${encodeURIComponent(String(limit))}`,
    method: "GET",
  });
}

export async function completeMockPayment(
  paymentId: string,
  status: "paid" | "failed" | "expired",
): Promise<BillingPayment> {
  return platformJson<BillingPayment>({
    path: `/billing/payments/${paymentId}/mock-complete`,
    method: "POST",
    body: { status },
  });
}

export type ProfileAddonQuote = {
  current_channels: number;
  addon_channels: number;
  new_total_channels: number;
  monthly_addon_cents: number;
  capped_by_tier: boolean;
  next_tier_channels: number | null;
  next_tier_monthly_cents: number | null;
  max_addon_channels_remaining: number;
  base_monthly_cents: number;
  base_plan_channels: number;
};

export async function getProfileAddonQuote(addonChannels = 2): Promise<ProfileAddonQuote> {
  return platformJson<ProfileAddonQuote>({
    path: `/licenses/profile-addon-quote?addon_channels=${encodeURIComponent(String(addonChannels))}`,
    method: "GET",
  });
}

export async function createProfileAddonPayment(addonChannels = 2): Promise<BillingPayment> {
  return platformJson<BillingPayment>({
    path: "/billing/profile-addon/payments",
    method: "POST",
    body: { addon_channels: addonChannels },
  });
}

export async function createCreditPackPayment(packId: string): Promise<BillingPayment> {
  return platformJson<BillingPayment>({
    path: "/billing/credit-pack/payments",
    method: "POST",
    body: { pack_id: packId },
  });
}

export async function schedulePlanDowngrade(planId: string): Promise<{
  status: string;
  effective_at: string;
  pending_plan_id: string;
}> {
  return platformJson({
    path: "/billing/schedule-downgrade",
    method: "POST",
    body: { plan_id: planId },
  });
}

export async function completeAddonOnboarding(): Promise<void> {
  await platformJson({
    path: "/licenses/complete-addon-onboarding",
    method: "POST",
  });
}
