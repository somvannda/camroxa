/**
 * Where a build talks to the platform.
 *
 * A packaged app defaults to production; an unpackaged dev run defaults to the
 * local API so `npm run dev` keeps working. `CAMXORA_API_BASE_URL` and
 * `CAMXORA_PORTAL_BASE_URL` still override both (sandbox dev, E2E, hotfix
 * builds).
 */
import { app } from "electron";

export const PRODUCTION_API_BASE_URL = "https://api.camxora.com/api/v1";
export const PRODUCTION_PORTAL_BASE_URL = "https://app.camxora.com";
export const LOCAL_API_BASE_URL = "http://127.0.0.1:8000/api/v1";

function cleanUrl(value: string | undefined): string {
  return (value ?? "").trim().replace(/\/+$/, "");
}

export function resolveApiBaseUrl(): string {
  const configured = cleanUrl(process.env.CAMXORA_API_BASE_URL);
  if (configured) return configured;
  return app.isPackaged ? PRODUCTION_API_BASE_URL : LOCAL_API_BASE_URL;
}

export function resolvePortalBaseUrl(): string {
  return cleanUrl(process.env.CAMXORA_PORTAL_BASE_URL) || PRODUCTION_PORTAL_BASE_URL;
}
