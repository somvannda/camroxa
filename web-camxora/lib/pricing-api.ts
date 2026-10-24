import { musicAuthFetch } from "@/lib/auth-fetch";

export type CreditPack = {
  id: string;
  slug: string;
  name: string;
  description: string;
  total_credits: number;
  price_cents: number;
  display_order: number;
  songs_equivalent: number;
};

export type FreePlan = {
  name: string;
  monthly_credits: number;
  credits_per_generate?: number;
};

type CheckoutResponse = {
  checkout_url: string;
  payment_id: string;
  expires_at?: string;
  qr_string?: string;
};

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const data = (await response.json()) as {
      detail?: string | { message?: string };
      error?: { message?: string };
    };
    if (typeof data.detail === "string") return data.detail;
    if (data.detail && typeof data.detail === "object" && "message" in data.detail) {
      return data.detail.message || fallback;
    }
    if (data.error?.message) return data.error.message;
  } catch {
    /* ignore */
  }
  return fallback;
}

export async function fetchCreditPacks(): Promise<CreditPack[]> {
  const response = await musicAuthFetch("/api/v3/topups/packs/public", { method: "GET" });
  if (!response.ok) {
    throw new Error(await readError(response, `Could not load credit packs (${response.status})`));
  }
  const data = (await response.json()) as { packs?: CreditPack[] };
  return Array.isArray(data.packs) ? data.packs : [];
}

export async function fetchFreePlan(): Promise<FreePlan | null> {
  const response = await musicAuthFetch("/api/v3/plans/public", { method: "GET" });
  if (!response.ok) return null;
  const data = (await response.json()) as Array<{
    name?: string;
    price_cents?: number;
    monthly_credits?: number;
    credits_per_generate?: number;
  }>;
  const free = Array.isArray(data) ? data.find((plan) => Number(plan.price_cents ?? 0) <= 0) : null;
  if (!free) return null;
  return {
    name: free.name || "Free",
    monthly_credits: Number(free.monthly_credits ?? 0),
    credits_per_generate: Number(free.credits_per_generate ?? 10),
  };
}

export function isAllowedCheckoutUrl(url: string | null | undefined): boolean {
  try {
    const parsed = new URL(String(url || ""));
    if (parsed.protocol !== "https:") return false;
    if (parsed.username || parsed.password) return false;
    const host = parsed.hostname.toLowerCase();
    return (
      host === "cutluy.com" ||
      host.endsWith(".cutluy.com") ||
      host === "chmaba.com" ||
      host.endsWith(".chmaba.com")
    );
  } catch {
    return false;
  }
}

async function readCheckout(response: Response, fallback: string): Promise<string> {
  if (!response.ok) {
    throw new Error(await readError(response, fallback));
  }
  const data = (await response.json()) as CheckoutResponse;
  if (!isAllowedCheckoutUrl(data.checkout_url)) {
    throw new Error("Checkout returned an untrusted payment URL.");
  }
  return data.checkout_url;
}

export async function purchaseTopup(packSlug: string): Promise<string> {
  const origin = window.location.origin;
  const response = await musicAuthFetch("/api/v3/topups/purchase", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      pack_slug: packSlug,
      success_url: `${origin}/pricing`,
      cancel_url: `${origin}/pricing`,
    }),
  });
  return readCheckout(response, "Could not start checkout.");
}
