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

/** Shape of GET /me/credits (unified credits-only wallet). */
export type MeCreditsResponse = {
  user_id?: string;
  balance_credits: number;
  balance_units?: number;
  grant_remaining_credits?: number;
  grant_remaining_units?: number;
  lots?: Array<{
    id: string;
    tag: string;
    amount_credits: number;
    remaining_credits: number;
    expires_at?: string | null;
    period_start?: string | null;
  }>;
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
  // The unified wallet is the credits-only source of truth (`/me/credits`).
  // `/credits/balance` is the legacy CutLuy ledger; keep it only for the ledger rows.
  const [wallet, ledger] = await Promise.all([
    platformJson<MeCreditsResponse>({ path: "/me/credits", method: "GET" }).catch(() => null),
    platformJson<WalletBalanceResponse>({ path: "/credits/balance", method: "GET" }).catch(() => null),
  ]);
  return {
    balance: wallet?.balance_credits ?? ledger?.balance ?? 0,
    plan_quota_remaining:
      wallet?.grant_remaining_credits ?? ledger?.plan_quota_remaining ?? null,
    recent_transactions: ledger?.recent_transactions ?? [],
  };
}
