/** Browser auth against same-origin /api (nginx → platform_api) so cookies stay on music.*. */

export type MusicUser = {
  id: string;
  email: string;
  display_name: string;
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

function apiPath(path: string): string {
  return path.startsWith('/') ? path : `/${path}`;
}

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const data = (await response.json()) as {
      detail?: string;
      error?: { message?: string };
    };
    if (data.detail) return data.detail;
    if (data.error?.message) return data.error.message;
  } catch {
    /* ignore */
  }
  return fallback;
}

export async function loginMusicUser(input: {
  email: string;
  password: string;
}): Promise<TokenResponse> {
  const response = await fetch(apiPath('/api/v1/auth/login'), {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-Portal-Context': 'user',
    },
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
}): Promise<void> {
  const response = await fetch(apiPath('/api/v1/auth/register'), {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-Portal-Context': 'user',
      'X-Signup-Product': 'music_web',
    },
    body: JSON.stringify({ ...input, product: 'music_web' }),
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Sign up failed (${response.status})`));
  }
}

export async function fetchMusicUser(): Promise<MusicUser | null> {
  const response = await fetch(apiPath('/api/v1/users/me'), {
    method: 'GET',
    credentials: 'include',
    headers: { 'X-Portal-Context': 'user' },
  });
  if (response.status === 401) return null;
  if (!response.ok) {
    throw new Error(await readError(response, `Session check failed (${response.status})`));
  }
  const data = (await response.json()) as MusicUser;
  return {
    id: data.id,
    email: data.email,
    display_name: data.display_name || data.email,
    email_confirmed: data.email_confirmed,
    products: Array.isArray((data as MusicUser).products) ? (data as MusicUser).products : [],
    plan_name: (data as MusicUser).plan_name ?? null,
  };
}

export async function logoutMusicUser(): Promise<void> {
  const response = await fetch(apiPath('/api/v1/auth/logout'), {
    method: 'POST',
    credentials: 'include',
    headers: { 'X-Portal-Context': 'user' },
  });
  if (!response.ok && response.status !== 401) {
    throw new Error(await readError(response, `Sign out failed (${response.status})`));
  }
}
