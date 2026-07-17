/**
 * Resolve API base URL for Admin Portal.
 * In dev and production, prefer same-origin (empty base) so /api is proxied and
 * auth cookies stay first-party. Set VITE_API_BASE_URL only when the API is on
 * a different host without a reverse-proxy /api route.
 */
export function resolveApiBaseUrl(): string {
  if (import.meta.env.DEV) {
    return '';
  }
  return String(import.meta.env.VITE_API_BASE_URL ?? '').trim();
}