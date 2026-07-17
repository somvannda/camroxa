"use client";

import { platformJson } from "@/lib/auth-fetch";

const PENDING_REDEEM_CODE_KEY = "camxora.pending_redeem_code";

export type RedeemCodePreview = {
  id: string;
  code: string;
  description: string | null;
  reward_type: "discount_amount" | "discount_percentage" | "credit_grant";
  discount_amount_cents: number | null;
  discount_percent: number | null;
  credit_amount: number | null;
  applicable_plan_id: string | null;
  applicable_plan_name: string | null;
  max_redemptions: number | null;
  current_redemptions: number;
  remaining_redemptions: number | null;
  per_user_limit: number;
  user_redemptions: number;
  is_active: boolean;
  starts_at: string | null;
  expires_at: string | null;
  applied_discount: boolean;
  base_amount_cents: number | null;
  best_public_amount_cents: number | null;
  final_amount_cents: number | null;
  savings_cents: number | null;
  message: string | null;
  new_balance?: number | null;
};

export type RedeemHistoryItem = {
  id: string;
  redeem_code_id: string;
  code: string;
  description: string | null;
  reward_type: "discount_amount" | "discount_percentage" | "credit_grant";
  user_id: string;
  user_email: string | null;
  user_display_name: string | null;
  billing_payment_id: string | null;
  plan_id: string | null;
  plan_name: string | null;
  status: string;
  amount_cents: number | null;
  credit_amount: number | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

export async function previewRedeemCode(input: {
  code: string;
  planId?: string | null;
}): Promise<RedeemCodePreview> {
  return platformJson<RedeemCodePreview>({
    path: "/redeem-codes/preview",
    method: "POST",
    body: {
      code: input.code,
      plan_id: input.planId ?? null,
    },
    auth: false,
  });
}

export async function redeemUserCode(code: string): Promise<RedeemCodePreview> {
  return platformJson<RedeemCodePreview>({
    path: "/redeem-codes/redeem",
    method: "POST",
    body: { code },
  });
}

export async function listMyRedeemHistory(limit = 8): Promise<RedeemHistoryItem[]> {
  return platformJson<RedeemHistoryItem[]>({
    path: `/redeem-codes/my-redemptions?limit=${encodeURIComponent(String(limit))}`,
    method: "GET",
  });
}

export function loadPendingRedeemCode(): string {
  if (typeof window === "undefined") {
    return "";
  }
  return String(window.localStorage.getItem(PENDING_REDEEM_CODE_KEY) ?? "").trim();
}

export function savePendingRedeemCode(code: string): void {
  if (typeof window === "undefined") {
    return;
  }
  const normalized = code.trim().toUpperCase();
  if (!normalized) {
    window.localStorage.removeItem(PENDING_REDEEM_CODE_KEY);
    return;
  }
  window.localStorage.setItem(PENDING_REDEEM_CODE_KEY, normalized);
}

export function clearPendingRedeemCode(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(PENDING_REDEEM_CODE_KEY);
}
