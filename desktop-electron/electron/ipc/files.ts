import { BrowserWindow, dialog, ipcMain } from "electron";
import { z } from "zod";
import { allowPickedFile, createMediaUrl } from "../services/media";
import { ok } from "../shared/types";
import { toError } from "./errors";

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
      return ok({ url: createMediaUrl(input.path) });
    } catch (error) {
      return toError(error);
    }
  });
}
