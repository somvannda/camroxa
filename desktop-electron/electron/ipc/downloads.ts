/**
 * IPC surface for the P4 music download coordinator.
 *
 * The coordinator owns the network, the disk and the retry policy, so every
 * handler here is thin. Only the shell window may call these channels; the
 * download URL never reaches the renderer.
 */
import fs from "node:fs";
import path from "node:path";
import { BrowserWindow, ipcMain, shell } from "electron";
import { z } from "zod";
import { apiRequest } from "../services/api-client";
import {
  DownloadCoordinator,
  type DownloadFetchResult,
} from "../services/download-coordinator";
import { createNodeDownloadIo } from "../services/download-io";
import { getDevicePreferences } from "../services/device-settings";
import { getAppPaths } from "../services/paths";
import { isPathInside } from "../services/media-utils";
import { logger } from "../services/logger";
import { fail, ok } from "../shared/types";
import { toError } from "./errors";

const DOWNLOAD_TIMEOUT_MS = 5 * 60_000;
const keySchema = z.object({ key: z.string().min(1).max(200) }).strict();

let coordinator: DownloadCoordinator | null = null;

function resolveDownloadRoot(): { root: string; managed: boolean } {
  const configured = getDevicePreferences().sunoOutputDir.trim();
  if (configured && path.isAbsolute(configured)) {
    return { root: path.resolve(configured), managed: false };
  }
  return { root: getAppPaths().downloads, managed: true };
}

/**
 * Streams the URL the server handed out. The session token is deliberately not
 * attached: a signed download URL must stand on its own, and a malformed server
 * value must never receive the account bearer token.
 */
async function fetchDownload(url: string, signal: AbortSignal): Promise<DownloadFetchResult> {
  const response = await fetch(url, {
    method: "GET",
    redirect: "follow",
    signal: AbortSignal.any([signal, AbortSignal.timeout(DOWNLOAD_TIMEOUT_MS)]),
    headers: {
      Accept: "audio/mpeg,audio/*;q=0.9,*/*;q=0.5",
      "X-Camxora-Client": "desktop",
    },
  });
  const rawLength = response.headers.get("content-length");
  const total = rawLength === null ? Number.NaN : Number(rawLength);
  return {
    status: response.status,
    ok: response.ok,
    totalBytes: Number.isFinite(total) && total > 0 ? total : null,
    body: response.body as unknown as AsyncIterable<Uint8Array> | null,
  };
}

export interface DownloadsIpcOptions {
  getWindow: () => BrowserWindow | null;
}

export function registerDownloadsIpc(options: DownloadsIpcOptions): void {
  if (coordinator) return;
  const getShellWindow = options.getWindow;
  const shellOnly = (senderId: number): boolean => {
    const window = getShellWindow();
    const contents = window?.webContents;
    return Boolean(contents && !contents.isDestroyed() && contents.id === senderId);
  };

  const instance = new DownloadCoordinator({
    fetchPending: async (limit) => {
      const response = await apiRequest({
        method: "GET",
        path: "/music/downloads/pending",
        query: { limit },
      });
      return response.data;
    },
    fetchDownload,
    io: createNodeDownloadIo(),
    resolveRoot: resolveDownloadRoot,
    reportDownloads: async (items) => {
      const grouped = new Map<
        string,
        {
          task_id: string;
          downloaded_primary?: boolean;
          downloaded_secondary?: boolean;
          output_dir_primary?: string;
          output_dir_secondary?: string;
        }
      >();
      for (const item of items) {
        const entry = grouped.get(item.taskId) ?? { task_id: item.taskId };
        if (item.role === "primary") {
          entry.downloaded_primary = true;
          entry.output_dir_primary = item.outputDir;
        } else {
          entry.downloaded_secondary = true;
          entry.output_dir_secondary = item.outputDir;
        }
        grouped.set(item.taskId, entry);
      }
      await apiRequest({
        method: "POST",
        path: "/music/downloads/sync",
        body: { items: [...grouped.values()] },
      });
    },
    allowLoopbackHttp: () => process.env.CAMXORA_E2E === "1",
    emit: (event) => notify(event),
    logger,
    concurrency: Number(process.env.CAMXORA_DOWNLOAD_CONCURRENCY ?? "") || undefined,
  });
  coordinator = instance;

  let notifyTimer: NodeJS.Timeout | null = null;
  let pendingEvent: { reason: string; key: string | null } | null = null;

  function notify(event: { reason: string; key: string | null }): void {
    pendingEvent = event;
    if (notifyTimer) return;
    notifyTimer = setTimeout(() => {
      notifyTimer = null;
      const payload = pendingEvent;
      pendingEvent = null;
      const window = getShellWindow();
      if (!window || window.webContents.isDestroyed()) return;
      window.webContents.send("downloads:changed", payload);
    }, 150);
  }

  ipcMain.handle("downloads:list", (event) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      instance.requestPoll();
      return ok(instance.snapshot());
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("downloads:start", (event) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      instance.start();
      return ok(instance.snapshot());
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("downloads:stop", (event) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      instance.stop();
      return ok(instance.snapshot());
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("downloads:retry", (event, payload: unknown) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      const input = keySchema.parse(payload);
      const outcome = instance.retry(input.key);
      if (!outcome.ok) return fail(outcome.error.code, outcome.error.message);
      return ok(instance.snapshot());
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("downloads:cancel", (event, payload: unknown) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      const input = keySchema.parse(payload);
      const outcome = instance.cancel(input.key);
      if (!outcome.ok) return fail(outcome.error.code, outcome.error.message);
      return ok(instance.snapshot());
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("downloads:reveal", (event, payload: unknown) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      const input = keySchema.parse(payload);
      const item = instance.item(input.key);
      if (!item) return fail("DOWNLOAD_NOT_FOUND", "That download is no longer tracked.");
      if (item.state !== "done" || !item.targetPath) {
        return fail("DOWNLOAD_NOT_READY", "That song has not finished downloading yet.");
      }
      const { root } = resolveDownloadRoot();
      if (!isPathInside(root, item.targetPath)) {
        return fail("DOWNLOAD_TARGET_OUTSIDE", "That file is outside the Suno output folder.");
      }
      if (!fs.existsSync(item.targetPath)) {
        return fail("DOWNLOAD_FILE_MISSING", "The downloaded file is no longer on this computer.");
      }
      shell.showItemInFolder(item.targetPath);
      return ok(true);
    } catch (error) {
      return toError(error);
    }
  });

  instance.start();
  logger.info("download coordinator started");
}

/** Abort active streams, delete partial files, then stop polling (app quit). */
export function stopDownloadCoordinator(): void {
  coordinator?.dispose();
  coordinator = null;
}

export function getDownloadCoordinator(): DownloadCoordinator | null {
  return coordinator;
}
