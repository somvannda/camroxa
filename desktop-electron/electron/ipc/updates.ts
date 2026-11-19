import { ipcMain } from "electron";
import { z } from "zod";
import { checkForUpdate, openUpdateDownload } from "../services/updates";
import { fail, ok } from "../shared/types";
import { toError } from "./errors";

const openUpdateSchema = z.object({
  version: z.string().min(1),
  url: z.string().url().optional(),
  mandatory: z.boolean().optional(),
  notes: z.string().optional(),
});

export function registerUpdatesIpc(): void {
  ipcMain.handle("updates:check", async () => {
    try {
      return ok(await checkForUpdate());
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("updates:open", async (_event, payload: unknown) => {
    try {
      const input = openUpdateSchema.parse(payload);
      const opened = await openUpdateDownload({
        version: input.version,
        url: input.url,
        mandatory: input.mandatory ?? false,
        notes: input.notes,
      });
      return opened
        ? ok(true)
        : fail("UPDATE_URL_MISSING", "This update has no download link yet.");
    } catch (error) {
      return toError(error);
    }
  });
}
