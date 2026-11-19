/**
 * IPC surface for the manual YouTube upload (Progress row action).
 *
 * Thin by design: validate the row, ask the main-process service, return a
 * typed result. The access token never crosses this boundary and the shell only
 * ever sees byte progress, phases, the video URL and readable reasons.
 */
import type { BrowserWindow } from "electron";
import { ipcMain } from "electron";
import { z } from "zod";
import { logger } from "../services/logger";
import { YoutubeUploadService, errorText } from "../services/youtube-upload";
import { fail, ok, type YoutubeUploadChangedEvent } from "../shared/types";

const rowSchema = z
  .object({
    key: z.string().min(1).max(500),
    batchId: z.string().min(1).max(200),
    profileId: z.string().min(1).max(200),
    role: z.string().max(40),
    runDir: z.string().max(4096).nullable(),
    youtubeUrl: z.string().max(2048).nullable().optional(),
  })
  .strict();

const availabilitySchema = z.object({ rows: z.array(rowSchema).max(200) }).strict();

const planSchema = z.object({ row: rowSchema }).strict();

const startSchema = z
  .object({
    key: z.string().min(1).max(500),
    batchId: z.string().min(1).max(200),
    profileId: z.string().min(1).max(200),
    role: z.string().max(40),
    runDir: z.string().max(4096).nullable(),
    playlist: z.string().max(200).optional(),
    retryJobUid: z.string().max(200).nullable().optional(),
  })
  .strict();

const cancelSchema = z.object({ uploadId: z.string().max(200).optional() }).strict();

export interface YoutubeIpcOptions {
  getWindow: () => BrowserWindow | null;
}

export function registerYoutubeIpc(options: YoutubeIpcOptions): void {
  const getWindow = options.getWindow;
  const shellOnly = (senderId: number): boolean => {
    const window = getWindow();
    const contents = window?.webContents;
    return Boolean(contents && !contents.isDestroyed() && contents.id === senderId);
  };

  const service = new YoutubeUploadService({
    emit: (upload) => {
      const window = getWindow();
      if (!window || window.webContents.isDestroyed()) return;
      const event: YoutubeUploadChangedEvent = { upload };
      window.webContents.send("youtube:changed", event);
      if (upload.phase === "done" || upload.phase === "failed" || upload.phase === "cancelled") {
        // A finished attempt changes the channel/quota picture for the page.
        service.invalidate();
      }
    },
  });

  ipcMain.handle("youtube:availability", async (event, payload: unknown) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    let request: z.infer<typeof availabilitySchema>;
    try {
      request = availabilitySchema.parse(payload ?? { rows: [] });
    } catch {
      return fail("INVALID_REQUEST", "The upload lookup is not valid.");
    }
    try {
      return ok(await service.availability(request.rows));
    } catch (error) {
      logger.warn("youtube availability failed", { error: errorText(error) });
      return fail("YOUTUBE_LOOKUP_FAILED", errorText(error));
    }
  });

  ipcMain.handle("youtube:plan", async (event, payload: unknown) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    let request: z.infer<typeof planSchema>;
    try {
      request = planSchema.parse(payload);
    } catch {
      return fail("INVALID_REQUEST", "The upload request is not valid.");
    }
    try {
      return ok(await service.plan(request.row));
    } catch (error) {
      return fail("YOUTUBE_UPLOAD_UNAVAILABLE", errorText(error));
    }
  });

  ipcMain.handle("youtube:start", async (event, payload: unknown) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    let request: z.infer<typeof startSchema>;
    try {
      request = startSchema.parse(payload);
    } catch {
      return fail("INVALID_REQUEST", "The upload request is not valid.");
    }
    try {
      return ok(await service.start(request));
    } catch (error) {
      const message = errorText(error);
      if (/already running/i.test(message)) {
        return fail("YOUTUBE_UPLOAD_BUSY", message);
      }
      return fail("YOUTUBE_UPLOAD_UNAVAILABLE", message);
    }
  });

  ipcMain.handle("youtube:cancel", (event, payload: unknown) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    let request: z.infer<typeof cancelSchema>;
    try {
      request = cancelSchema.parse(payload ?? {});
    } catch {
      return fail("INVALID_REQUEST", "The cancel request is not valid.");
    }
    return ok({ cancelled: service.cancel(request.uploadId) });
  });

  ipcMain.handle("youtube:state", (event) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    return ok(service.snapshot());
  });
}
