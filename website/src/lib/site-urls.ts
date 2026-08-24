/** Public site URLs — set via NEXT_PUBLIC_* in .env.production per environment. */

export function isSandboxEnvironment(): boolean {
  return (process.env.NEXT_PUBLIC_CAMXORA_ENV ?? "").trim().toLowerCase() === "sandbox";
}

export function getWebsiteBaseUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_SITE_URL ?? process.env.NEXT_PUBLIC_WEBSITE_URL;
  if (fromEnv?.trim()) {
    return fromEnv.trim().replace(/\/$/, "");
  }
  if (process.env.NODE_ENV === "development") {
    return "http://localhost:3000";
  }
  if (isSandboxEnvironment()) {
    return "https://sandbox.camxora.com";
  }
  return "https://camxora.com";
}

export function getMusicWebBaseUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_MUSIC_WEB_URL;
  if (fromEnv?.trim()) {
    return fromEnv.trim().replace(/\/$/, "");
  }
  if (process.env.NODE_ENV === "development") {
    return "http://localhost:3002";
  }
  if (isSandboxEnvironment()) {
    return "https://music.sandbox.camxora.com";
  }
  return "https://music.camxora.com";
}

export function getUserPortalBaseUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_USER_PORTAL_URL;
  if (fromEnv?.trim()) {
    return fromEnv.trim().replace(/\/$/, "");
  }
  if (process.env.NODE_ENV === "development") {
    return "http://localhost:3001";
  }
  if (isSandboxEnvironment()) {
    return "https://app.sandbox.camxora.com";
  }
  return "https://app.camxora.com";
}
