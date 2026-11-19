import { BrowserWindow, ipcMain } from "electron";
import { z } from "zod";
import { createMediaUrl } from "../services/media";
import { getAppPaths } from "../services/paths";
import {
  deleteVideoTemplate,
  listVideoTemplates,
  readVideoTemplate,
  type VideoTemplateSummary,
} from "../services/video-templates";
import { fail, ok, type VideoTemplateChangedEvent, type VideoTemplateInfo } from "../shared/types";
import { toError } from "./errors";

const idSchema = z.object({ id: z.string().min(1).max(200) });

function shellOnly(event: Electron.IpcMainInvokeEvent): boolean {
  return Boolean(BrowserWindow.fromWebContents(event.sender));
}

/** Shell-facing summary with an opaque media URL for the thumbnail. */
export function toVideoTemplateInfo(entry: VideoTemplateSummary): VideoTemplateInfo {
  let thumbnailUrl: string | null = null;
  if (entry.thumbnailPath) {
    try {
      thumbnailUrl = createMediaUrl(entry.thumbnailPath);
    } catch {
      thumbnailUrl = null;
    }
  }
  return {
    id: entry.id,
    name: entry.name,
    kind: entry.kind,
    width: entry.output.width,
    height: entry.output.height,
    fps: entry.output.fps,
    createdAt: entry.createdAt,
    thumbnailUrl,
  };
}

/** Tell every shell window that the saved-template library changed. */
export function notifyVideoTemplatesChanged(event: VideoTemplateChangedEvent): void {
  for (const window of BrowserWindow.getAllWindows()) {
    if (!window.webContents.isDestroyed()) {
      window.webContents.send("video-templates:changed", event);
    }
  }
}

export function registerVideoTemplatesIpc(): void {
  ipcMain.handle("video-templates:list", (event) => {
    if (!shellOnly(event)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      return ok(listVideoTemplates(getAppPaths().templates).map(toVideoTemplateInfo));
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("video-templates:read", (event, payload: unknown) => {
    if (!shellOnly(event)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      const { id } = idSchema.parse(payload);
      const detail = readVideoTemplate(getAppPaths().templates, id);
      return ok({
        ...toVideoTemplateInfo(detail),
        pipeline: detail.pipeline,
      });
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("video-templates:delete", (event, payload: unknown) => {
    if (!shellOnly(event)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      const { id } = idSchema.parse(payload);
      const deleted = deleteVideoTemplate(getAppPaths().templates, id);
      if (deleted) notifyVideoTemplatesChanged({ id, action: "deleted" });
      return ok(deleted);
    } catch (error) {
      return toError(error);
    }
  });
}
