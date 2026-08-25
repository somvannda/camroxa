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
