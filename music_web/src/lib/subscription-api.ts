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
  daily_credits?: number;
  lyric_credits?: number;
  music_credits?: number;
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
  grant_remaining?: number;
  breakdown: {
    monthly: number;
    topup: number;
    daily_free: number;
  };
};

export type V3WalletView = {
  balance_credits?: number;
  grant_remaining_credits?: number;
  plan?: {
    name?: string;
    monthly_credits?: number;
    daily_credits?: number;
  } | null;
  lots?: Array<{
    tag?: string;
    remaining_credits?: number;
  }>;
};

function asCredits(value: unknown): number {
  const n = Number(value);
  return Number.isFinite(n) ? Math.max(0, Math.round(n)) : 0;
}

export function mergeV3CreditBalance(
  v3: V3WalletView | null,
  v2: CreditBalance | null,
): CreditBalance | null {
  if (!v3 && !v2) return null;

  const v3Balance = asCredits(v3?.balance_credits);
  const grantRemaining = asCredits(v3?.grant_remaining_credits);
  const planMonthly = asCredits(v3?.plan?.monthly_credits);
  const planDaily = asCredits(v3?.plan?.daily_credits);
  const dailyLot = (v3?.lots ?? [])
    .filter((lot) => String(lot.tag || '') === 'daily_grant')
    .reduce((sum, lot) => sum + asCredits(lot.remaining_credits), 0);

  const hasPaidWeb = Boolean(v2?.has_subscription);
  const hasPaidPlan = hasPaidWeb || planMonthly > 0 || grantRemaining > 0;
  const total = v3Balance;
  const dailyLimit = planDaily || asCredits(v2?.daily_free_limit);
  const dailyRemaining = dailyLot || (!hasPaidPlan ? v3Balance : 0);

  return {
    total_credits: total,
    monthly_credits: planMonthly || grantRemaining || asCredits(v2?.monthly_credits),
    monthly_credits_used: Math.max(0, (planMonthly || asCredits(v2?.monthly_credits)) - grantRemaining),
    topup_credits: hasPaidWeb && v3Balance <= 0
      ? asCredits(v2?.topup_credits)
      : Math.max(0, v3Balance - grantRemaining - dailyRemaining),
    daily_free_credits: dailyRemaining,
    daily_free_limit: dailyLimit,
    daily_free_used: Math.max(0, dailyLimit - dailyRemaining),
    has_subscription: hasPaidPlan,
    current_period_end: v2?.current_period_end ?? null,
    reset_at: v2?.reset_at ?? null,
    grant_remaining: grantRemaining,
    breakdown: {
      monthly: grantRemaining,
      topup: Math.max(0, total - grantRemaining - dailyRemaining),
      daily_free: dailyRemaining,
    },
  };
}

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

type PublicPlanRow = {
  id: string;
  name?: string;
  daily_credits?: number;
  monthly_credits?: number;
  lyric_credits?: number;
  music_credits?: number;
  price_cents?: number;
  billing_cycle_days?: number;
  is_public?: boolean;
  is_active?: boolean;
};

function asPublicRows(payload: unknown): PublicPlanRow[] {
  if (Array.isArray(payload)) return payload as PublicPlanRow[];
  if (payload && typeof payload === 'object') {
    const rec = payload as { plans?: unknown; data?: unknown };
    if (Array.isArray(rec.plans)) return rec.plans as PublicPlanRow[];
    if (Array.isArray(rec.data)) return rec.data as PublicPlanRow[];
  }
  return [];
}

function overlayPublicPlan(plan: SubscriptionPlan, pub?: PublicPlanRow): SubscriptionPlan {
  if (!pub) {
    return {
      ...plan,
      daily_credits: Number(plan.daily_credits || 0),
      lyric_credits: Number(plan.lyric_credits || 0),
      music_credits: Number(plan.music_credits || 0),
    };
  }
  return {
    ...plan,
    daily_credits: Number(pub.daily_credits ?? plan.daily_credits ?? 0),
    monthly_credits: Number(plan.monthly_credits || pub.monthly_credits || 0),
    lyric_credits: Number(pub.lyric_credits ?? plan.lyric_credits ?? 0),
    music_credits: Number(pub.music_credits ?? plan.music_credits ?? 0),
  };
}

async function fetchPublicPlanRows(): Promise<PublicPlanRow[]> {
  for (const path of ['/api/v3/plans/public', '/api/v1/plans/public'] as const) {
    try {
      const rows = asPublicRows(await apiFetch<unknown>(path));
      if (rows.length) return rows;
    } catch {
      /* try unauthenticated public catalog */
    }
    try {
      const response = await fetch(path, { credentials: 'include' });
      if (!response.ok) continue;
      const rows = asPublicRows(await response.json());
      if (rows.length) return rows;
    } catch {
      /* try next public catalog */
    }
  }
  return [];
}

export async function fetchSubscriptionPlans(): Promise<{ plans: SubscriptionPlan[] }> {
  let data: { plans: SubscriptionPlan[] } = { plans: [] };
  try {
    data = await apiFetch<{ plans: SubscriptionPlan[] }>(`${API_V2}/subscriptions/plans`);
    if (!data || !Array.isArray(data.plans)) data = { plans: [] };
  } catch {
    data = { plans: [] };
  }
  const publicRows = await fetchPublicPlanRows();
  const byId = new Map(publicRows.map((row) => [row.id, row]));
  const byName = new Map(publicRows.map((row) => [(row.name || '').toLowerCase(), row]));
  const merged = data.plans.map((plan) =>
    overlayPublicPlan(plan, byId.get(plan.id) || byName.get(plan.name.toLowerCase())),
  );
  const known = new Set(merged.map((plan) => plan.id));
  for (const row of publicRows) {
    if (row.is_public === false || row.is_active === false) continue;
    if (known.has(row.id)) continue;
    merged.push({
      id: row.id,
      name: row.name || 'Plan',
      price_cents: Number(row.price_cents || 0),
      billing_cycle: Number(row.billing_cycle_days || 30) >= 365 ? 'yearly' : 'monthly',
      monthly_credits: Number(row.monthly_credits || 0),
      daily_credits: Number(row.daily_credits || 0),
      lyric_credits: Number(row.lyric_credits || 0),
      music_credits: Number(row.music_credits || 0),
      features: [],
      display_order: 0,
      is_public: true,
    });
    known.add(row.id);
  }
  return { plans: merged };
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
  try {
    const v3 = await apiFetch<V3WalletView>('/api/v3/me/credits');
    const mapped = mergeV3CreditBalance(v3, null);
    if (!mapped) {
      throw new Error('Failed to load credits');
    }
    return mapped;
  } catch {
    return apiFetch<CreditBalance>(`${API_V2}/credits/balance`);
  }
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
export const PUBLIC_CARD_BULLETS = [
  'Web Create',
  'Desktop studio',
  'Dual channels',
  'Top-up packs',
] as const;

export const FREE_CARD_BULLETS = [
  'Web Create',
  'Daily credit reset',
  'Top-up packs',
] as const;

export function cardBulletsForPlan(plan: { name: string; price_cents: number }): readonly string[] {
  const name = plan.name.replace(/[_-]/g, ' ').toLowerCase();
  if (plan.price_cents <= 0 && name.includes('free')) {
    return FREE_CARD_BULLETS;
  }
  return PUBLIC_CARD_BULLETS;
}

export function creditsToSongs(credits: number): number {
  return Math.floor(Math.max(0, Number(credits) || 0) / 10);
}

export function isHiddenLegacyPrice(plan: { price_cents: number }): boolean {
  return Number(plan.price_cents) === 7900;
}

export function publicPaidPlans(plans: SubscriptionPlan[]): SubscriptionPlan[] {
  return plans.filter((plan) => plan.is_public && plan.price_cents > 0 && !isHiddenLegacyPrice(plan));
}

export function publicFreePlan(plans: SubscriptionPlan[]): SubscriptionPlan | undefined {
  return plans.find(
    (plan) => plan.is_public && plan.price_cents <= 0 && /free/i.test(plan.name),
  );
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
