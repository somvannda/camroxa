/**
 * Route-prefix classification for the deny-by-default auth backstop.
 *
 * Kept in a config-free module so the policy can be unit-tested directly and so
 * there is a single definition of "which surfaces must be authenticated".
 */

/** Prefixes that must never be reachable without a valid session or API key. */
export const PROTECTED_PREFIXES = ["/me/", "/v1/", "/api/", "/admin/", "/payments/"] as const;

/**
 * Protected-prefix routes that authenticate by another means. Provider webhooks
 * carry an HMAC signature, not a session, so they are exempt. Keep this list
 * minimal — anything else added here is intentionally public.
 */
export const PUBLIC_PROTECTED_ROUTES: ReadonlySet<string> = new Set([
  "POST /payments/chmaba/webhook",
]);

/** True when `path` (query already stripped) is under a protected prefix. */
export function isProtectedPath(path: string): boolean {
  return PROTECTED_PREFIXES.some((prefix) => path.startsWith(prefix));
}

/** True when this method + path is an explicit public exception under a protected prefix. */
export function isPublicProtectedRoute(method: string, path: string): boolean {
  return PUBLIC_PROTECTED_ROUTES.has(`${method} ${path}`);
}
