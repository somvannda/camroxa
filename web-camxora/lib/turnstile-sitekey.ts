const SANDBOX_TURNSTILE_SITE_KEY = "0x4AAAAAAERrvCRyn8xcIet3";

export function resolveTurnstileSiteKey(
  configured: string | null | undefined,
  nodeEnv: string | null | undefined,
): string {
  const key = (configured ?? "").trim();
  if (key) return key;
  return nodeEnv === "development" ? SANDBOX_TURNSTILE_SITE_KEY : "";
}
