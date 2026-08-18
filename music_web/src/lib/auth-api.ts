/** Browser auth against same-origin /api (nginx → platform_api) so cookies stay on music.*. */

import { apiPath, musicAuthFetch } from '@/lib/auth-fetch';

export type MusicUser = {
  id: string;
  email: string;
  display_name: string;
  avatar_url?: string | null;
  email_confirmed?: boolean;
  products?: string[];
  plan_name?: string | null;
};

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const data = (await response.json()) as {
      detail?: string | { msg?: string; message?: string }[];
      error?: { message?: string; code?: string; details?: { fields?: Array<{ message?: string }> } };
    };
    if (data.error?.code === 'GEO_BLOCKED') {
      return data.error.message || 'This service is only available in Cambodia.';
    }
    if (data.error?.code === 'GENERATION_FROZEN') {
      return data.error.message || 'Music generation is paused. Try again later.';
    }
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail) && data.detail[0]?.msg) return data.detail[0].msg;
    if (data.detail && typeof data.detail === 'object' && 'message' in data.detail) {
      const message = (data.detail as { message?: string }).message;
      if (message) return message;
    }
    if (data.error?.details?.fields?.[0]?.message) return data.error.details.fields[0].message;
    if (data.error?.message) return data.error.message;
  } catch {
    /* ignore */
  }
  return fallback;
}

export async function loginMusicUser(input: {
  email: string;
  password: string;
  cf_turnstile_response?: string;
}): Promise<TokenResponse> {
  const response = await musicAuthFetch('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Sign in failed (${response.status})`));
  }
  return (await response.json()) as TokenResponse;
}

export async function registerMusicUser(input: {
  email: string;
  password: string;
  display_name: string;
  cf_turnstile_response?: string;
}): Promise<void> {
  const response = await musicAuthFetch('/api/v1/auth/register', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Signup-Product': 'music_web',
    },
    body: JSON.stringify({ ...input, product: 'music_web' }),
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Sign up failed (${response.status})`));
  }
}

export async function sendVerificationEmail(email: string): Promise<{ message: string }> {
  const response = await musicAuthFetch('/api/v1/auth/send-verification', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Could not send verification code (${response.status})`));
  }
  return (await response.json()) as { message: string };
}

export async function verifyEmailCode(input: {
  email: string;
  code: string;
}): Promise<{ message: string; is_verified?: boolean }> {
  const response = await musicAuthFetch('/api/v1/auth/verify-email', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Verification failed (${response.status})`));
  }
  return (await response.json()) as { message: string; is_verified?: boolean };
}

export async function fetchMusicUser(): Promise<MusicUser | null> {
  const response = await musicAuthFetch('/api/v1/users/me', { method: 'GET' });
  if (response.status === 401) return null;
  if (!response.ok) {
    throw new Error(await readError(response, `Session check failed (${response.status})`));
  }
  const data = (await response.json()) as MusicUser;
  return {
    id: data.id,
    email: data.email,
    display_name: data.display_name || data.email,
    avatar_url: (data as MusicUser).avatar_url ?? null,
    email_confirmed: data.email_confirmed,
    products: Array.isArray((data as MusicUser).products) ? (data as MusicUser).products : [],
    plan_name: (data as MusicUser).plan_name ?? null,
  };
}

export function getUserAvatarUrl(userId: string, cacheKey?: string | number | null): string {
  const suffix = cacheKey ? `?v=${encodeURIComponent(String(cacheKey))}` : '';
  return apiPath(`/api/v1/media/users/${encodeURIComponent(userId)}/avatar${suffix}`);
}

export async function updateMusicUserProfile(input: {
  display_name?: string;
}): Promise<MusicUser> {
  const response = await musicAuthFetch('/api/v1/users/me', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Profile update failed (${response.status})`));
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
  };
}

export async function uploadMusicUserAvatar(file: File): Promise<MusicUser> {
  const formData = new FormData();
  formData.append('file', file);
  const response = await musicAuthFetch('/api/v1/users/me/avatar', {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Photo upload failed (${response.status})`));
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
  };
}

export async function logoutMusicUser(): Promise<void> {
  const response = await musicAuthFetch('/api/v1/auth/logout', { method: 'POST' });
  if (!response.ok && response.status !== 401) {
    throw new Error(await readError(response, `Sign out failed (${response.status})`));
  }
}
