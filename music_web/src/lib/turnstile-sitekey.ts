/**
 * Turnstile sitekey resolution.
 *
 * The sitekey is baked into the bundle at build time. The sandbox key is only
 * acceptable for local development: a production build once shipped it, Cloudflare
 * rejected the widget for the hostname, and every user was locked out of login.
 * See `docs/changelog/2026-10-05-music-web-turnstile-login-lockout.md`.
 */

/** Sitekey valid only for `music.sandbox.camxora.com` and localhost. */
export const SANDBOX_TURNSTILE_SITE_KEY = '0x4AAAAAAERrvCRyn8xcIet3';

/**
 * Resolve the sitekey to render with.
 *
 * Returns the configured key when present. Otherwise, in development only, the
 * sandbox key; in every other environment an empty string so the widget renders
 * a visible error instead of a widget that cannot work.
 */
export function resolveTurnstileSiteKey(
  configured: string | null | undefined,
  nodeEnv: string | null | undefined,
): string {
  const key = (configured ?? '').trim();
  if (key) {
    return key;
  }
  return nodeEnv === 'development' ? SANDBOX_TURNSTILE_SITE_KEY : '';
}

/** True when `key` is the sandbox key, which must never ship to production. */
export function isSandboxTurnstileSiteKey(key: string | null | undefined): boolean {
  return (key ?? '').trim() === SANDBOX_TURNSTILE_SITE_KEY;
}
