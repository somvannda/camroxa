/** Resolve platform API base URL for server-side website fetches. */
export function resolvePlatformApiBaseUrl(): string {
  const configured = (
    process.env.NEXT_PUBLIC_PLATFORM_API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    ""
  ).trim();

  if (configured) {
    return configured.replace(/\/$/, "");
  }

  if (process.env.NODE_ENV === "development") {
    return "http://localhost:8000/api/v1";
  }

  return "https://api.camxora.com/api/v1";
}
