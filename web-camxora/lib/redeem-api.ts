import { musicAuthFetch } from "@/lib/auth-fetch";

export type RedeemResult = {
  id: string;
  code: string;
  description?: string | null;
  reward_type: string;
  credit_amount?: number | null;
  new_balance?: number | null;
  message?: string | null;
};

export type RedeemHistoryItem = {
  id: string;
  code: string;
  description?: string | null;
  reward_type: string;
  credit_amount?: number | null;
  status: string;
  created_at: string;
};

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const data = (await response.json()) as {
      detail?: string | { message?: string };
      error?: { message?: string };
    };
    if (typeof data.detail === "string") return data.detail;
    if (data.detail && typeof data.detail === "object" && data.detail.message) {
      return data.detail.message;
    }
    if (data.error?.message) return data.error.message;
  } catch {
    /* ignore */
  }
  return fallback;
}

export async function redeemCode(code: string): Promise<RedeemResult> {
  const response = await musicAuthFetch("/api/v3/redeem-codes/redeem", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Could not redeem code (${response.status})`));
  }
  return (await response.json()) as RedeemResult;
}

export async function fetchRedeemHistory(limit = 10): Promise<RedeemHistoryItem[]> {
  const response = await musicAuthFetch(
    `/api/v3/redeem-codes/my-redemptions?limit=${limit}`
  );
  if (!response.ok) return [];
  const data = (await response.json()) as RedeemHistoryItem[];
  return Array.isArray(data) ? data : [];
}
