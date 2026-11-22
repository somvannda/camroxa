/**
 * Human label for the API a build points at. Pure, so it can be unit-tested
 * without Electron.
 */
export type ApiEnvironment = "sandbox" | "local" | "production" | "development";

export function classifyApiEnvironment(apiBaseUrl: string): ApiEnvironment {
  let host = "";
  try {
    host = new URL(apiBaseUrl).hostname.toLowerCase();
  } catch {
    host = "";
  }
  if (host.includes("sandbox")) return "sandbox";
  if (host === "localhost" || host === "127.0.0.1" || host === "::1") return "local";
  if (host === "api.camxora.com" || host.endsWith(".api.camxora.com")) return "production";
  return "development";
}
