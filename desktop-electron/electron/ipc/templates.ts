import { ipcMain } from "electron";
import { z } from "zod";
import {
  installTemplate,
  listInstalledTemplates,
  loadMarketplacePreview,
  TemplateInstallError,
} from "../services/templates";
import { fail, ok } from "../shared/types";
import { toError } from "./errors";
import { notifyVideoTemplatesChanged } from "./video-templates";

const installSchema = z.object({
  itemId: z.string().min(1).max(200),
  name: z.string().max(300).optional(),
  kind: z.string().max(60).optional(),
  previewUrl: z.string().max(2000).optional(),
  reinstall: z.boolean().optional(),
});

const previewSchema = z.object({
  itemId: z.string().min(1).max(200),
  url: z.string().max(2000),
});

function toTemplateError(error: unknown) {
  if (error instanceof TemplateInstallError) {
    return fail(error.code, error.message, undefined, error.retryable);
  }
  return toError(error);
}

export function registerTemplatesIpc(): void {
  ipcMain.handle("templates:list", () => {
    try {
      return ok(listInstalledTemplates());
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("templates:install", async (_event, payload: unknown) => {
    try {
      const request = installSchema.parse(payload);
      const result = await installTemplate(request);
      // The Studio picker lists installed folders, so refresh it right away.
      notifyVideoTemplatesChanged({ id: result.uid, action: "saved" });
      return ok(result);
    } catch (error) {
      return toTemplateError(error);
    }
  });

  ipcMain.handle("templates:preview", async (_event, payload: unknown) => {
    try {
      const input = previewSchema.parse(payload);
      return ok({ dataUrl: await loadMarketplacePreview(input.itemId, input.url) });
    } catch (error) {
      return toTemplateError(error);
    }
  });
}
