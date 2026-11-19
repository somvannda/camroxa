import { shell } from "electron";
import { logger } from "./logger";
import { getApiBaseUrl } from "./api-client";
import { getStore } from "./store";
import { APP_VERSION } from "../shared/version";
import type { UpdateCheckResult, UpdateOffer } from "../shared/types";

const DEFAULT_TIMEOUT_MS = 10_000;
const STORED_OFFER_KEY = "updates.mandatory";

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
  download_url?: unknown;
  release_notes?: unknown;
  published_at?: unknown;
}

export function parseUpdateManifest(
  payload: unknown,
  currentVersion = APP_VERSION,
): UpdateOffer | null {
  if (!payload || typeof payload !== "object") return null;
  const raw = payload as ManifestPayload;
  if (typeof raw.version !== "string" || !raw.version.trim()) return null;
  if (compareVersions(raw.version, currentVersion) <= 0) return null;
  const candidateUrl = raw.url ?? raw.download_url;
  const url =
    typeof candidateUrl === "string" && /^https:\/\//i.test(candidateUrl)
      ? candidateUrl
      : undefined;
  const candidateNotes = raw.notes ?? raw.release_notes;
  const candidatePublished = raw.publishedAt ?? raw.published_at;
  return {
    version: raw.version.trim(),
    mandatory: raw.mandatory === true,
    notes: typeof candidateNotes === "string" ? candidateNotes : undefined,
    url,
    publishedAt: typeof candidatePublished === "string" ? candidatePublished : undefined,
  };
}

function readStoredMandatory(): UpdateOffer | null {
  try {
    const raw = getStore().getMeta(STORED_OFFER_KEY);
    if (!raw) return null;
    const offer = parseUpdateManifest(JSON.parse(raw), APP_VERSION);
    return offer?.mandatory ? offer : null;
  } catch {
    return null;
  }
}

function storeMandatory(offer: UpdateOffer | null): void {
  try {
    const store = getStore();
    if (offer?.mandatory) {
      store.setMeta(STORED_OFFER_KEY, JSON.stringify(offer));
    } else {
      store.setMeta(STORED_OFFER_KEY, "");
    }
  } catch {
    // A missing store must never turn an update check into a crash.
  }
}

export async function checkForUpdate(): Promise<UpdateCheckResult> {
  const manifestUrl = (process.env.CAMXORA_UPDATE_MANIFEST_URL ?? "").trim();
  const target = manifestUrl || `${getApiBaseUrl()}/public/desktop-release`;

  if (manifestUrl) {
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
  }

  try {
    const response = await fetch(target, {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
    });
    // A confirmed 404 is the published-release withdrawal signal: no offer,
    // no error, and any persisted mandatory gate is cleared.
    if (response.status === 404) {
      storeMandatory(null);
      return { currentVersion: APP_VERSION, offer: null };
    }
    if (!response.ok) {
      const stored = readStoredMandatory();
      return {
        currentVersion: APP_VERSION,
        offer: stored,
        message: `Update check failed (${response.status}).`,
      };
    }
    const offer = parseUpdateManifest(await response.json());
    storeMandatory(offer?.mandatory ? offer : null);
    logger.info("update check completed", {
      current: APP_VERSION,
      offered: offer?.version ?? null,
      mandatory: offer?.mandatory ?? false,
      source: manifestUrl ? "manifest" : "api",
    });
    return { currentVersion: APP_VERSION, offer };
  } catch (error) {
    logger.warn("update check unavailable", { error: String(error) });
    return {
      currentVersion: APP_VERSION,
      offer: readStoredMandatory(),
      message: "Cannot reach the update service right now.",
    };
  }
}

export async function openUpdateDownload(offer: UpdateOffer): Promise<boolean> {  if (!offer.url || !/^https:\/\//i.test(offer.url)) return false;
  await shell.openExternal(offer.url);
  return true;
}
