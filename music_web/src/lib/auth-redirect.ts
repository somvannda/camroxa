export const DEFAULT_POST_AUTH_PATH = '/create';

const AUTH_PATHS = new Set(['/login', '/register', '/verify-email']);

function normalizePath(raw: string): string {
  const pathOnly = raw.split('?')[0]?.split('#')[0] ?? '';
  if (pathOnly.length > 1 && pathOnly.endsWith('/')) {
    return pathOnly.slice(0, -1);
  }
  return pathOnly;
}

export function isAuthPath(pathname: string): boolean {
  return AUTH_PATHS.has(normalizePath(pathname));
}

/** Safe in-app destination after login / signup / email confirm. Never returns an auth page. */
export function safeNextPath(raw: string | null | undefined): string {
  if (!raw) return DEFAULT_POST_AUTH_PATH;
  if (!raw.startsWith('/') || raw.startsWith('//')) return DEFAULT_POST_AUTH_PATH;
  const path = normalizePath(raw);
  if (!path || AUTH_PATHS.has(path)) return DEFAULT_POST_AUTH_PATH;
  return path;
}

type SignedInUser = {
  email?: string | null;
  email_confirmed?: boolean;
};

/**
 * Where a signed-in session should go instead of /login or /register.
 * Unconfirmed accounts continue email verification; everyone else goes to Create
 * (or a safe ?next=). Returns null when there is no session.
 */
export function destinationForSignedInUser(
  user: SignedInUser | null | undefined,
  next: string = DEFAULT_POST_AUTH_PATH,
): string | null {
  if (!user) return null;
  const dest = safeNextPath(next);
  if (user.email_confirmed === false) {
    const params = new URLSearchParams();
    const email = user.email?.trim() ?? '';
    if (email) params.set('email', email);
    params.set('next', dest);
    return `/verify-email?${params.toString()}`;
  }
  return dest;
}
