import fs from "node:fs";
import path from "node:path";
import { BrowserWindow, dialog, ipcMain, shell } from "electron";
import { z } from "zod";
import { apiRequestBytes } from "../services/api-client";
import { allowPickedFile, createMediaUrl } from "../services/media";
import { isPathInside, mimeFor } from "../services/media-utils";
import { resolveUserPath, userDataRoot } from "../services/user-paths";import { fail, ok } from "../shared/types";
import { toError } from "./errors";

const IMAGE_EXTENSIONS = new Set([".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"]);
const MAX_IMAGE_BYTES = 25 * 1024 * 1024;

const pathSchema = z.object({
  path: z.string().min(1),
});

const pickFileSchema = z.object({
  kind: z.enum(["file", "directory"]),
  title: z.string().optional(),
  filters: z
    .array(z.object({ name: z.string(), extensions: z.array(z.string()) }))
    .optional(),
  multiple: z.boolean().optional(),
});

const mediaUrlSchema = z.object({
  path: z.string().min(1),
});

const imageJobSchema = z.object({
  jobId: z.string().min(1).max(100),
  path: z.string().max(4096).optional(),
});

export function registerFilesIpc(): void {
  ipcMain.handle("files:pick", async (event, payload: unknown) => {
    try {
      const input = pickFileSchema.parse(payload);
      const window = BrowserWindow.fromWebContents(event.sender);
      const options = {
        title: input.title,
        properties: [
          input.kind === "directory" ? "openDirectory" : "openFile",
          ...(input.multiple ? ["multiSelections" as const] : []),
        ] as Array<"openFile" | "openDirectory" | "multiSelections">,
        filters: input.filters,
      };
      const result = window
        ? await dialog.showOpenDialog(window, options)
        : await dialog.showOpenDialog(options);
      if (result.canceled) return ok([]);
      for (const filePath of result.filePaths) allowPickedFile(filePath);
      return ok(result.filePaths);
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("media:url", async (_event, payload: unknown) => {
    try {
      const input = mediaUrlSchema.parse(payload);
      return ok({ url: createMediaUrl(resolveUserPath(input.path)) });
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("files:open", async (_event, payload: unknown) => {
    try {
      const input = pathSchema.parse(payload);
      const result = await shell.openPath(resolveUserPath(input.path));
      return result ? fail("OPEN_FAILED", result) : ok(true);
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("files:reveal", (_event, payload: unknown) => {
    try {
      const input = pathSchema.parse(payload);
      shell.showItemInFolder(resolveUserPath(input.path));
      return ok(true);
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("files:ensure-dir", (_event, payload: unknown) => {
    try {
      const input = pathSchema.parse(payload);
      const resolved = resolveUserPath(input.path);
      fs.mkdirSync(resolved, { recursive: true });
      return ok(resolved);
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("files:read-image", async (_event, payload: unknown) => {
    try {
      const input = pathSchema.parse(payload);
      const resolved = resolveUserPath(input.path);
      const extension = path.extname(resolved).toLowerCase();
      if (!IMAGE_EXTENSIONS.has(extension)) {
        return fail("UNSUPPORTED_IMAGE", "Only image files can be previewed.");
      }
      const stat = fs.statSync(resolved);
      if (!stat.isFile()) return fail("NOT_A_FILE", "That path is not a file.");
      if (stat.size > MAX_IMAGE_BYTES) {
        return fail("IMAGE_TOO_LARGE", "That image is too large to preview.");
      }
      const bytes = fs.readFileSync(resolved);
      return ok({
        name: path.basename(resolved),
        mime: mimeFor(resolved),
        bytes: new Uint8Array(bytes),
      });
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("files:read-image-job", async (_event, payload: unknown) => {
    try {
      const input = imageJobSchema.parse(payload);
      const target = input.path ? resolveUserPath(input.path) : "";
      if (target) {
        try {
          const stat = fs.statSync(target);
          if (stat.isFile() && stat.size > 0) {
            return ok({
              name: path.basename(target),
              mime: mimeFor(target),
              bytes: new Uint8Array(fs.readFileSync(target)),
            });
          }
        } catch {
          // Not cached locally yet; fetch the durable server copy below.
        }
      }

      const response = await apiRequestBytes({
        method: "GET",
        path: `/image-jobs/${encodeURIComponent(input.jobId)}/output`,
      });
      if (response.bytes.byteLength > 0 && target && isPathInside(userDataRoot(), target)) {
        // Cache the generated image beside the run audio so the auto-video
        // coordinator can use it as a background later.
        try {
          fs.mkdirSync(path.dirname(target), { recursive: true });
          fs.writeFileSync(target, response.bytes);
        } catch {
          // Preview still works when the cache write fails.
        }
      }
      return ok({
        name: target ? path.basename(target) : `${input.jobId}.png`,
        mime: response.contentType?.split(";")[0]?.trim() || "image/png",
        bytes: response.bytes,
      });
    } catch (error) {
      return toError(error);
    }
  });
}
