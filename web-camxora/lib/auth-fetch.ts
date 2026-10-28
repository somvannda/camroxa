const USER_CONTEXT_HEADER = "X-Portal-Context";

const SKIP_REFRESH_PATHS = [
  "/api/v3/auth/login",
  "/api/v3/auth/register",
  "/api/v3/auth/refresh",
];

export function apiPath(path: string): string {
  return path.startsWith("/") ? path : `/${path}`;
}

function shouldSkipRefresh(path: string): boolean {
  const normalized = apiPath(path).split("?")[0] ?? path;
  return SKIP_REFRESH_PATHS.includes(normalized);
}

let refreshPromise: Promise<boolean> | null = null;

const REFRESH_LOCK_NAME = "camxora.auth.refresh";
const LAST_REFRESH_KEY = "camxora.auth.lastRefresh";
const REFRESH_GRACE_MS = 3_000;

type LockManagerLike = {
  request: <T>(name: string, callback: () => Promise<T>) => Promise<T>;
};

async function performRefresh(): Promise<boolean> {
  try {
    const last = Number(window.localStorage.getItem(LAST_REFRESH_KEY) || 0);
    if (last && Date.now() - last < REFRESH_GRACE_MS) {
      // Another tab just refreshed. Retry the request with the new cookies.
      return true;
    }
  } catch {
    /* localStorage can be unavailable in privacy modes. */
  }

  try {
    const response = await fetch(apiPath("/api/v3/auth/refresh"), {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        [USER_CONTEXT_HEADER]: "user",
      },
      body: "{}",
    });
    if (response.ok) {
      try {
        window.localStorage.setItem(LAST_REFRESH_KEY, String(Date.now()));
      } catch {
        /* ignore */
      }
    }
    return response.ok;
  } catch {
    return false;
  }
}

async function refreshAccessCookie(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const locks = (navigator as Navigator & { locks?: LockManagerLike }).locks;
      if (locks?.request) {
        // Serialize refresh across tabs so two tabs never rotate the same
        // refresh token at once and trigger reuse detection.
        return locks.request(REFRESH_LOCK_NAME, performRefresh);
      }
      return performRefresh();
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

export async function musicAuthFetch(
  path: string,
  init: RequestInit = {}
): Promise<Response> {
  const url = apiPath(path);
  const headers = new Headers(init.headers);
  if (!headers.has(USER_CONTEXT_HEADER)) {
    headers.set(USER_CONTEXT_HEADER, "user");
  }

  const requestInit: RequestInit = {
    ...init,
    credentials: "include",
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
