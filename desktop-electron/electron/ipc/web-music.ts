/**
 * Simple-mode web-music downloads.
 *
 * The web `/web-music/generations/{id}/download` routes need the account
 * bearer token, so the renderer cannot stream them directly. The main process
 * fetches the file, writes it to the managed download folder and hands back a
 * `camxora-media://` URL the player can use without ever seeing the token.
 */
import fs from "node:fs";
import path from "node:path";
import { ipcMain } from "electron";
import { z } from "zod";
import { getApiBaseUrl } from "../services/api-client";
import { getDevicePreferences } from "../services/device-settings";
import { allowPickedFile, createMediaUrl } from "../services/media";
import { getAppPaths } from "../services/paths";
import { sessionStore } from "../services/session";
import { fail, ok } from "../shared/types";
import { toError } from "./errors";

const DOWNLOAD_TIMEOUT_MS = 3 * 60_000;

const saveSchema = z
  .object({
    taskId: z.string().min(1).max(80),
    variant: z.enum(["ok", "alt"]),
    title: z.string().max(200).optional(),
    format: z.enum(["mp3", "wav"]).default("mp3"),
  })
  .strict();

function resolveDownloadRoot(): string {
  const configured = getDevicePreferences().sunoOutputDir.trim();
  if (configured && path.isAbsolute(configured)) return path.resolve(configured);
  return getAppPaths().downloads;
}

function safeStem(title: string | undefined, taskId: string): string {
  const base = (title ?? "").trim() || `song-${taskId.slice(0, 8)}`;
  const cleaned = base
    .split("")
    .filter((char) => char.charCodeAt(0) > 31)
    .join("")
    .replace(/[<>:"/\\|?*]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80);
  return cleaned || `song-${taskId.slice(0, 8)}`;
}

export function registerWebMusicIpc(): void {
  ipcMain.handle("webmusic:save-clip", async (_event, payload: unknown) => {
    try {
      const input = saveSchema.parse(payload);
      const tokens = sessionStore.load();
      if (!tokens?.accessToken) {
        return fail("UNAUTHORIZED", "Sign in to download songs.");
      }

      const suffix = input.format === "wav" ? "download-wav" : "download";
      const url =
        `${getApiBaseUrl()}/web-music/generations/${encodeURIComponent(input.taskId)}` +
        `/${suffix}?variant=${input.variant}`;

      const response = await fetch(url, {
        method: "GET",
        headers: {
          Accept: "audio/mpeg,audio/wav,audio/*;q=0.9,*/*;q=0.5",
          Authorization: `Bearer ${tokens.accessToken}`,
          "X-Camxora-Client": "desktop",
        },
        signal: AbortSignal.timeout(DOWNLOAD_TIMEOUT_MS),
      });
      if (!response.ok) {
        return fail(
          response.status === 401 ? "UNAUTHORIZED" : "DOWNLOAD_FAILED",
          response.status === 401
            ? "Session expired. Sign in again."
            : `The song download failed (${response.status}).`,
        );
      }

      const root = resolveDownloadRoot();
      fs.mkdirSync(root, { recursive: true });
      const extension = input.format === "wav" ? "wav" : "mp3";
      const variantLabel = input.variant === "alt" ? "alt" : "primary";
      let target = path.join(
        root,
        `${safeStem(input.title, input.taskId)} (${variantLabel}).${extension}`,
      );
      let counter = 2;
      while (fs.existsSync(target)) {
        target = path.join(
          root,
          `${safeStem(input.title, input.taskId)} (${variantLabel} ${counter}).${extension}`,
        );
        counter += 1;
      }

      const bytes = Buffer.from(await response.arrayBuffer());
      if (bytes.length === 0) {
        return fail("DOWNLOAD_EMPTY", "The song download was empty.");
      }
      fs.writeFileSync(target, bytes);

      allowPickedFile(target);
      return ok({ path: target, url: createMediaUrl(target) });
    } catch (error) {
      return toError(error);
    }
  });
}
