/** Subscription and credit management API client (`/api/v2`) */

import { musicAuthFetch } from '@/lib/auth-fetch';

const API_V2 = '/api/v2';

// ============================================================================
// Types
// ============================================================================

export type SubscriptionPlan = {
  id: string;
  name: string;
  price_cents: number;
  billing_cycle: 'monthly' | 'yearly';
  monthly_credits: number;
  features: string[];
  display_order: number;
  is_public: boolean;
};

export type UserSubscription = {
  id: string;
  user_id: string;
  plan_id: string;
  plan_name: string;
  status: 'active' | 'cancelled' | 'expired' | 'past_due';
  billing_cycle: 'monthly' | 'yearly';
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  monthly_credits_granted: number;
  monthly_credits_used: number;
  topup_credits_balance: number;
  total_credits_available: number;
  created_at: string;
  cancelled_at?: string | null;
};

export type CreditBalance = {
  total_credits: number;
  monthly_credits: number;
  monthly_credits_used: number;
  topup_credits: number;
  daily_free_credits: number;
  daily_free_limit: number;
  daily_free_used: number;
  has_subscription: boolean;
  current_period_end?: string | null;
  reset_at?: string | null;
  breakdown: {
    monthly: number;
    topup: number;
    daily_free: number;
  };
};

export type CreditTransaction = {
  id: string;
  wallet_id: string;
  amount: number;
  transaction_type: 'grant' | 'consume' | 'refund' | 'adjustment';
  description: string;
  reference_id?: string | null;
  balance_after: number;
  created_at: string;
};

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

export type TopupPurchase = {
  id: string;
  pack_name: string;
  credits_purchased: number;
  amount_paid_cents: number;
  payment_status: 'pending' | 'completed' | 'failed' | 'refunded';
  purchased_at: string;
};

// ============================================================================
// Utilities
// ============================================================================

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const data = (await response.json()) as {
      detail?: string;
      error?: { message?: string; code?: string };
    };
    if (data.error?.message) return data.error.message;
    if (typeof data.detail === 'string') return data.detail;
  } catch {
    /* ignore */
  }
  return fallback;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await musicAuthFetch(path, init);

  if (!response.ok) {
    throw new Error(await readError(response, `Request failed (${response.status})`));
  }

  if (response.status === 204) return undefined as T;

  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) return undefined as T;

  return (await response.json()) as T;
}

// ============================================================================
// Subscription API
// ============================================================================

export async function fetchSubscriptionPlans(): Promise<{ plans: SubscriptionPlan[] }> {
  return apiFetch<{ plans: SubscriptionPlan[] }>(`${API_V2}/subscriptions/plans`);
}

export async function fetchMySubscription(): Promise<UserSubscription | null> {
  const data = await apiFetch<UserSubscription | { data?: UserSubscription | null } | null>(
    `${API_V2}/subscriptions/my-subscription`,
  );
  const nested =
    data && typeof data === 'object' && 'data' in data && data.data && typeof data.data === 'object'
      ? data.data
      : data;
  if (!nested || typeof nested !== 'object' || !('status' in nested)) return null;
  return nested as UserSubscription;
}

export async function purchaseSubscription(input: {
  plan_id: string;
  success_url: string;
  cancel_url: string;
}): Promise<{ checkout_url: string; payment_id: string; expires_at: string; qr_string?: string }> {
  return apiFetch(`${API_V2}/subscriptions/purchase`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
}

export async function cancelSubscription(input: {
  cancel_at_period_end?: boolean;
}): Promise<{ success: boolean; message: string; subscription: UserSubscription | null }> {
  return apiFetch(`${API_V2}/subscriptions/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
}

// ============================================================================
// Credit API
// ============================================================================

export async function fetchCreditBalance(): Promise<CreditBalance> {
  return apiFetch<CreditBalance>(`${API_V2}/credits/balance`);
}

export async function fetchCreditHistory(
  limit = 50,
  offset = 0,
): Promise<{ transactions: CreditTransaction[]; total: number; limit: number; offset: number }> {
  return apiFetch(`${API_V2}/credits/history?limit=${limit}&offset=${offset}`);
}

// ============================================================================
// Top-up API
// ============================================================================

export async function fetchCreditPacks(): Promise<{ packs: CreditPack[] }> {
  return apiFetch<{ packs: CreditPack[] }>(`${API_V2}/topups/packs`);
}

export async function purchaseTopup(input: {
  pack_slug: string;
  success_url: string;
  cancel_url: string;
}): Promise<{
  checkout_url: string;
  payment_id: string;
  expires_at: string;
  qr_string?: string;
  pack_name: string;
  credits: number;
  amount_cents: number;
}> {
  return apiFetch(`${API_V2}/topups/purchase`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
}

export type CheckoutStatus = {
  status: 'pending' | 'paid' | 'failed' | 'expired' | string;
  fulfilled: boolean;
  plan_name?: string;
  pack_name?: string;
  credits: number;
};

export function isAllowedCutluyCheckoutUrl(url: string | null | undefined): boolean {
  try {
    const parsed = new URL(String(url || ''));
    if (parsed.protocol !== 'https:') return false;
    if (parsed.username || parsed.password) return false;
    const host = parsed.hostname.toLowerCase();
    return host === 'cutluy.com' || host.endsWith('.cutluy.com');
  } catch {
    return false;
  }
}

export async function fetchSubscriptionCheckoutStatus(paymentId: string): Promise<CheckoutStatus> {
  return apiFetch(`${API_V2}/subscriptions/payments/${encodeURIComponent(paymentId)}`);
}

export async function fetchTopupCheckoutStatus(paymentId: string): Promise<CheckoutStatus> {
  return apiFetch(`${API_V2}/topups/payments/${encodeURIComponent(paymentId)}`);
}

export async function fetchTopupHistory(
  limit = 50,
  offset = 0,
): Promise<{ purchases: TopupPurchase[]; total: number; limit: number; offset: number }> {
  return apiFetch(`${API_V2}/topups/history?limit=${limit}&offset=${offset}`);
}

// ============================================================================
// Utility Functions
// ============================================================================

export function formatPlanDisplayName(planName: string): string {
  const trimmed = planName.trim();
  const prettyCycle = trimmed.match(/\((monthly|yearly)\)$/i);
  const slugCycle = trimmed.match(/[-_\s]+(monthly|yearly)$/i);
  const cycle = (prettyCycle?.[1] ?? slugCycle?.[1] ?? '').toLowerCase();
  const raw = trimmed
    .replace(/\s*\((monthly|yearly)\)$/i, '')
    .replace(/[-_\s]+(monthly|yearly)$/i, '')
    .replace(/_/g, ' ')
    .trim();
  const title = raw
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(' ');
  const label = title || 'Plan';
  if (cycle === 'monthly') return `${label} (Monthly)`;
  if (cycle === 'yearly') return `${label} (Yearly)`;
  return label;
}

export function parseBillingDate(value?: string | null): Date | null {
  if (!value || !value.trim()) return null;
  const direct = new Date(value);
  if (Number.isFinite(direct.getTime())) return direct;
  const normalized = value.trim().replace(' ', 'T').replace(/([+-]\d{2})$/, '$1:00');
  const retry = new Date(normalized);
  return Number.isFinite(retry.getTime()) ? retry : null;
}

export function matchCurrentPlan(
  plans: SubscriptionPlan[],
  subscription: UserSubscription | null,
  grantedCredits = 0,
): SubscriptionPlan | undefined {
  if (subscription?.plan_id) {
    const byId = plans.find((plan) => plan.id === subscription.plan_id);
    if (byId) return byId;
  }
  if (subscription?.plan_name) {
    const want = formatPlanDisplayName(subscription.plan_name).toLowerCase();
    const byName = plans.find(
      (plan) => formatPlanDisplayName(plan.name).toLowerCase() === want,
    );
    if (byName) return byName;
  }
  if (grantedCredits <= 0) return undefined;
  const cycle = subscription?.billing_cycle;
  const pool = cycle ? plans.filter((plan) => plan.billing_cycle === cycle) : plans;
  const closest = [...pool].sort(
    (a, b) =>
      Math.abs(a.monthly_credits - grantedCredits) - Math.abs(b.monthly_credits - grantedCredits),
  )[0];
  if (!closest) return undefined;
  const tolerance = Math.max(50, grantedCredits * 0.15);
  return Math.abs(closest.monthly_credits - grantedCredits) <= tolerance ? closest : undefined;
}

/**
 * Format credits as songs equivalent (10 credits = 1 song)
 */
export function creditsToSongs(credits: number): number {
  return Math.floor(credits / 10);
}

/**
 * Format price in cents to dollars
 */
export function formatPrice(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

/**
 * Calculate discount percentage
 */
export function calculateDiscount(monthlyPrice: number, yearlyPrice: number): number {
  const yearlyMonthlyEquivalent = monthlyPrice * 12;
  const discount = ((yearlyMonthlyEquivalent - yearlyPrice) / yearlyMonthlyEquivalent) * 100;
  return Math.round(discount);
}

/**
 * Check if user has sufficient credits
 */
export function hasSufficientCredits(balance: CreditBalance, requiredCredits: number): boolean {
  return balance.total_credits >= requiredCredits;
}
