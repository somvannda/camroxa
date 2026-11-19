import { ipcMain } from "electron";
import { z } from "zod";
import { apiRequest } from "../services/api-client";
import { ok } from "../shared/types";
import { toError } from "./errors";

const apiRequestSchema = z.object({
  method: z.enum(["GET", "POST", "PATCH", "PUT", "DELETE"]),
  path: z.string().min(1),
  query: z
    .record(z.string(), z.union([z.string(), z.number(), z.boolean(), z.undefined()]))
    .optional(),
  body: z.unknown().optional(),
  auth: z.boolean().optional(),
  timeoutMs: z.number().int().positive().max(600_000).optional(),
});

export function registerApiIpc(): void {
  ipcMain.handle("api:request", async (_event, payload: unknown) => {
    try {
      const request = apiRequestSchema.parse(payload);
      return ok(await apiRequest(request));
    } catch (error) {
      return toError(error);
    }
  });
}
