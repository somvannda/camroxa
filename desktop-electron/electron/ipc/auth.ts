import { ipcMain } from "electron";
import { z } from "zod";
import { login, restoreSession } from "../services/api-client";
import { logger } from "../services/logger";
import { sessionStore } from "../services/session";
import { ok } from "../shared/types";
import { toError } from "./errors";

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
  remember: z.boolean().optional().default(true),
});

export function registerAuthIpc(): void {
  ipcMain.handle("auth:login", async (_event, payload: unknown) => {
    try {
      const input = loginSchema.parse(payload);
      return ok(await login(input.email, input.password, input.remember));
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("auth:restore", () => ok(restoreSession()));

  ipcMain.handle("auth:logout", () => {
    sessionStore.clear();
    logger.info("user signed out");
    return ok(true);
  });

  ipcMain.handle("auth:saved-accounts", () => {
    const account = sessionStore.accountSummary();
    return ok(account ? [account] : []);
  });
}
