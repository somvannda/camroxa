/** Same-origin cookie auth: 401 → POST /auth/refresh → retry, matching user portal. */

const USER_CONTEXT_HEADER = 'X-Portal-Context';

const SKIP_REFRESH_PATHS = [
  '/api/v3/auth/login',
  '/api/v3/auth/register',
  '/api/v3/auth/refresh',
];

export function apiPath(path: string): string {
  return path.startsWith('/') ? path : `/${path}`;
}

function shouldSkipRefresh(path: string): boolean {
  const normalized = apiPath(path).split('?')[0] ?? path;
  return SKIP_REFRESH_PATHS.includes(normalized);
}

let refreshPromise: Promise<boolean> | null = null;

// `music.camxora.com` keeps polling license/credit endpoints every few seconds
// while signed out. Without this backoff every one of those 401s triggered a
// fresh `POST /auth/refresh` (which also 401s), producing thousands of useless
// auth calls a day. A rejected refresh (401/403) is remembered briefly; a
// network failure is not, so a real login is picked up immediately.
const REFRESH_REJECT_BACKOFF_MS = 60_000;
let refreshBlockedUntil = 0;

export function resetAuthRefreshState(): void {
  refreshPromise = null;
  refreshBlockedUntil = 0;
}

async function refreshAccessCookie(): Promise<boolean> {
  if (Date.now() < refreshBlockedUntil) {
    return false;
  }
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const response = await fetch(apiPath('/api/v3/auth/refresh'), {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            [USER_CONTEXT_HEADER]: 'user',
          },
          body: '{}',
        });
        if (response.ok) {
          refreshBlockedUntil = 0;
          return true;
        }
        if (response.status === 401 || response.status === 403) {
          refreshBlockedUntil = Date.now() + REFRESH_REJECT_BACKOFF_MS;
        }
        return false;
      } catch {
        return false;
      }
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

export async function musicAuthFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const url = apiPath(path);
  const headers = new Headers(init.headers);
  if (!headers.has(USER_CONTEXT_HEADER)) {
    headers.set(USER_CONTEXT_HEADER, 'user');
  }

  const requestInit: RequestInit = {
    ...init,
    credentials: 'include',
    headers,
  };

  let response = await fetch(url, requestInit);
  if (response.status === 401 && !shouldSkipRefresh(url)) {
    const refreshed = await refreshAccessCookie();
    if (refreshed) {
      response = await fetch(url, requestInit);
    }
  }
  return response;
}
