"use client";

import { platformJson } from "@/lib/auth-fetch";

export type WalletTransaction = {
  id: string;
  amount: number;
  amount_units?: number;
  direction: string;
  reason: string;
  purpose?: string | null;
  provider?: string | null;
  model?: string | null;
  operation?: string | null;
  ref_id?: string | null;
  payment_ref?: string | null;
  billing?: string | null;
  list_credit_units?: number | null;
  charged_credit_units?: number | null;
  coverage?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at?: string | null;
};

export type WalletBalanceResponse = {
  balance: number;
  plan_quota_remaining: number | null;
  recent_transactions: WalletTransaction[];
};

export type BillingMode = "plan_allowance" | "wallet" | "platform_absorb" | "other";

const MICRO_CREDIT = 10_000;

export function resolveBillingMode(tx: WalletTransaction): BillingMode {
  const billing =
    tx.billing ||
    (typeof tx.metadata?.billing === "string" ? tx.metadata.billing : null);
  if (billing === "plan_allowance") return "plan_allowance";
  if (billing === "platform_absorb") return "platform_absorb";
  if (billing === "wallet") return "wallet";
  if (tx.direction === "debit" && Math.abs(tx.amount) < 1e-12) return "plan_allowance";
  if (tx.direction === "debit" && Math.abs(tx.amount) >= 1e-12) return "wallet";
  return "other";
}

export function formatUsageTransactionLabel(tx: WalletTransaction): string {
  const billing = resolveBillingMode(tx);
  const listUnits =
    typeof tx.list_credit_units === "number"
      ? tx.list_credit_units
      : typeof tx.metadata?.list_credit_units === "number"
        ? tx.metadata.list_credit_units
        : null;
  const listCredits =
    listUnits != null
      ? (listUnits / MICRO_CREDIT).toLocaleString(undefined, { maximumFractionDigits: 6 })
      : null;

  if (billing === "plan_allowance") {
    return listCredits ? `Plan allowance (list ${listCredits})` : "Plan allowance";
  }
  if (billing === "platform_absorb") {
    return listCredits ? `Platform absorbed (list ${listCredits})` : "Platform absorbed";
  }
  if (billing === "wallet") {
    return "Credits charged";
  }
  if (tx.direction === "credit") return "Credit";
  if (tx.direction === "refund") return "Refund";
  return "Debit";
}

export async function getWalletBalance(): Promise<WalletBalanceResponse> {
  return platformJson<WalletBalanceResponse>({
    path: "/credits/balance",
    method: "GET",
  });
}
