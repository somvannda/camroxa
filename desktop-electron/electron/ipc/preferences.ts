import { ipcMain } from "electron";
import { z } from "zod";
import { getDevicePreferences, setDevicePreferences } from "../services/device-settings";
import { ok } from "../shared/types";
import { toError } from "./errors";

const devicePreferencesSchema = z.object({
  ffmpegPath: z.string().optional(),
  sunoOutputDir: z.string().optional(),
});

export function registerPreferencesIpc(): void {
  ipcMain.handle("preferences:device:get", async () => {
    try {
      return ok(getDevicePreferences());
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("preferences:device:set", async (_event, payload: unknown) => {
    try {
      const input = devicePreferencesSchema.parse(payload);
      return ok(setDevicePreferences(input));
    } catch (error) {
      return toError(error);
    }
  });
}
