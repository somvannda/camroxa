/** Public site URLs for music portal chrome. */
export function isSandboxEnvironment(): boolean {
  return (process.env.NEXT_PUBLIC_CAMXORA_ENV ?? '').trim().toLowerCase() === 'sandbox';
}

export function getUserPortalBaseUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_USER_PORTAL_URL?.replace(/\/$/, '');
  if (fromEnv) return fromEnv;
  return isSandboxEnvironment()
    ? 'https://app.sandbox.camxora.com'
    : 'https://app.camxora.com';
}

export function getWebsiteBaseUrl(): string {
  const fromEnv =
    process.env.NEXT_PUBLIC_WEBSITE_URL?.replace(/\/$/, '') ||
    process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, '');
  if (fromEnv) return fromEnv;
  return isSandboxEnvironment()
    ? 'https://sandbox.camxora.com'
    : 'https://camxora.com';
}
