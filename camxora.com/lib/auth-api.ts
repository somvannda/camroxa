import { musicAuthFetch } from "@/lib/auth-fetch";

export type MusicUser = {
  id: string;
  email: string;
  display_name: string;
  avatar_url?: string | null;
  email_confirmed?: boolean;
  products?: string[];
  plan_name?: string | null;
  credit_balance?: number;
};

export type CreditSummary = {
  total: number;
  planName: string | null;
  monthlyCredits: number | null;
  isFree: boolean;
  expiresAt: string | null;
  resetLabel: string | null;
};

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const data = (await response.json()) as {
      detail?: string | { message?: string }[] | { message?: string };
      error?: {
        message?: string;
        code?: string;
        details?: { fields?: Array<{ message?: string }> };
      };
    };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail) && data.detail[0]?.message) return data.detail[0].message;
    if (data.detail && typeof data.detail === "object" && "message" in data.detail) {
      return data.detail.message || fallback;
    }
    if (data.error?.details?.fields?.[0]?.message) {
      return data.error.details.fields[0].message;
    }
    if (data.error?.message) return data.error.message;
  } catch {
    /* ignore */
  }
  return fallback;
}

export async function loginMusicUser(input: {
  email: string;
  password: string;
  remember?: boolean;
  cf_turnstile_response?: string;
}): Promise<void> {
  const response = await musicAuthFetch("/api/v3/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Sign in failed (${response.status})`));
  }
}

export async function registerMusicUser(input: {
  email: string;
  password: string;
  display_name: string;
  invitation_code?: string;
  referral_code?: string;
  cf_turnstile_response?: string;
}): Promise<void> {
  const response = await musicAuthFetch("/api/v3/auth/register", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Signup-Product": "music_web",
    },
    body: JSON.stringify({ ...input, product: "music_web" }),
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Sign up failed (${response.status})`));
  }
}

export async function fetchMusicUser(): Promise<MusicUser | null> {
  const response = await musicAuthFetch("/api/v3/users/me", { method: "GET" });
  if (response.status === 401) return null;
  if (!response.ok) {
    throw new Error(await readError(response, `Session check failed (${response.status})`));
  }
  const data = (await response.json()) as MusicUser;
  return {
    id: data.id,
    email: data.email,
    display_name: data.display_name || data.email,
    avatar_url: data.avatar_url ?? null,
    email_confirmed: data.email_confirmed,
    products: Array.isArray(data.products) ? data.products : [],
    plan_name: data.plan_name ?? null,
    credit_balance: Number(data.credit_balance ?? 0),
  };
}

export async function fetchCreditSummary(): Promise<CreditSummary | null> {
  const response = await musicAuthFetch("/api/v3/me/credits", { method: "GET" });
  if (!response.ok) return null;
  const data = (await response.json()) as {
    balance_credits?: number;
    total_credits?: number;
    reset_label?: string | null;
    plan?: {
      name?: string;
      price_cents?: number;
      monthly_credits?: number;
    } | null;
    lots?: Array<{
      remaining_credits?: number;
      expires_at?: string | null;
    }>;
  };
  const total = Number(data.balance_credits ?? data.total_credits ?? 0);
  const expiries = (Array.isArray(data.lots) ? data.lots : [])
    .filter((lot) => Number(lot.remaining_credits ?? 0) > 0 && lot.expires_at)
    .map((lot) => String(lot.expires_at))
    .sort();
  const planName = data.plan?.name ?? null;
  const priceCents = Number(data.plan?.price_cents ?? 0);
  const monthlyCredits = Number(data.plan?.monthly_credits ?? 0);
  return {
    total: Number.isFinite(total) ? total : 0,
    planName,
    monthlyCredits: Number.isFinite(monthlyCredits) && monthlyCredits > 0 ? monthlyCredits : null,
    isFree: priceCents <= 0 || (planName ?? "").toLowerCase() === "free",
    expiresAt: expiries[0] ?? null,
    resetLabel: data.reset_label ?? null,
  };
}

export async function sendVerificationEmail(
  email: string
): Promise<{ message: string; is_verified?: boolean }> {
  const response = await musicAuthFetch("/api/v3/auth/send-verification", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Could not send code (${response.status})`));
  }
  return (await response.json()) as { message: string; is_verified?: boolean };
}

export async function verifyEmailCode(input: {
  email: string;
  code: string;
}): Promise<{ message: string; is_verified?: boolean }> {
  const response = await musicAuthFetch("/api/v3/auth/verify-email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Verification failed (${response.status})`));
  }
  return (await response.json()) as { message: string; is_verified?: boolean };
}

export async function forgotPassword(
  email: string
): Promise<{ message: string }> {
  const response = await musicAuthFetch("/api/v3/auth/forgot-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Could not send reset code (${response.status})`));
  }
  return (await response.json()) as { message: string };
}

export async function verifyResetCode(input: {
  email: string;
  code: string;
}): Promise<{ message: string; is_verified?: boolean }> {
  const response = await musicAuthFetch("/api/v3/auth/verify-reset-code", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Could not confirm reset code (${response.status})`));
  }
  return (await response.json()) as { message: string; is_verified?: boolean };
}

export async function resetPassword(input: {
  email: string;
  code: string;
  new_password: string;
}): Promise<{ message: string }> {
  const response = await musicAuthFetch("/api/v3/auth/reset-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Password reset failed (${response.status})`));
  }
  return (await response.json()) as { message: string };
}

export async function logoutMusicUser(): Promise<void> {
  const response = await musicAuthFetch("/api/v3/auth/logout", { method: "POST" });
  if (!response.ok && response.status !== 401) {
    throw new Error(await readError(response, `Sign out failed (${response.status})`));
  }
}
