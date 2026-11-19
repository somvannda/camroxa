import { shell } from "electron";
import { logger } from "./logger";
import { APP_VERSION } from "../shared/version";
import type { UpdateCheckResult, UpdateOffer } from "../shared/types";

const DEFAULT_TIMEOUT_MS = 10_000;

export function compareVersions(left: string, right: string): number {
  const parse = (value: string): number[] =>
    value
      .trim()
      .replace(/^v/i, "")
      .split(/[.+-]/)
      .map((part) => {
        const number = Number.parseInt(part, 10);
        return Number.isFinite(number) ? number : 0;
      });
  const a = parse(left);
  const b = parse(right);
  const length = Math.max(a.length, b.length);
  for (let index = 0; index < length; index += 1) {
    const diff = (a[index] ?? 0) - (b[index] ?? 0);
    if (diff !== 0) return diff > 0 ? 1 : -1;
  }
  return 0;
}

interface ManifestPayload {
  version?: unknown;
  mandatory?: unknown;
  notes?: unknown;
  url?: unknown;
  publishedAt?: unknown;
}

export function parseUpdateManifest(
  payload: unknown,
  currentVersion = APP_VERSION,
): UpdateOffer | null {
  if (!payload || typeof payload !== "object") return null;
  const raw = payload as ManifestPayload;
  if (typeof raw.version !== "string" || !raw.version.trim()) return null;
  if (compareVersions(raw.version, currentVersion) <= 0) return null;
  const url = typeof raw.url === "string" && /^https:\/\//i.test(raw.url) ? raw.url : undefined;
  return {
    version: raw.version.trim(),
    mandatory: raw.mandatory === true,
    notes: typeof raw.notes === "string" ? raw.notes : undefined,
    url,
    publishedAt: typeof raw.publishedAt === "string" ? raw.publishedAt : undefined,
  };
}

export async function checkForUpdate(): Promise<UpdateCheckResult> {
  const manifestUrl = (process.env.CAMXORA_UPDATE_MANIFEST_URL ?? "").trim();
  if (!manifestUrl) {
    return { currentVersion: APP_VERSION, offer: null };
  }
  const allowLoopbackHttp =
    process.env.CAMXORA_UPDATE_ALLOW_HTTP === "1" &&
    /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?\//i.test(manifestUrl);
  if (!/^https:\/\//i.test(manifestUrl) && !allowLoopbackHttp) {
    return {
      currentVersion: APP_VERSION,
      offer: null,
      message: "The update manifest URL must use HTTPS.",
    };
  }

  try {
    const response = await fetch(manifestUrl, {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
    });
    if (!response.ok) {
      return {
        currentVersion: APP_VERSION,
        offer: null,
        message: `Update check failed (${response.status}).`,
      };
    }
    const offer = parseUpdateManifest(await response.json());
    logger.info("update check completed", {
      current: APP_VERSION,
      offered: offer?.version ?? null,
      mandatory: offer?.mandatory ?? false,
    });
    return { currentVersion: APP_VERSION, offer };
  } catch (error) {
    logger.warn("update check unavailable", { error: String(error) });
    return {
      currentVersion: APP_VERSION,
      offer: null,
      message: "Cannot reach the update service right now.",
    };
  }
}

export async function openUpdateDownload(offer: UpdateOffer): Promise<boolean> {
  if (!offer.url || !/^https:\/\//i.test(offer.url)) return false;
  await shell.openExternal(offer.url);
  return true;
}
