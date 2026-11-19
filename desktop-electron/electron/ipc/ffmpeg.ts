import { ipcMain } from "electron";
import { z } from "zod";
import { cancelJob, checkFfmpeg, probe, runTranscode } from "../services/ffmpeg";
import { ok } from "../shared/types";
import { toError } from "./errors";

const ffprobeSchema = z.object({
  path: z.string().min(1),
});

const transcodeSchema = z.object({
  input: z.string().min(1),
  output: z.string().min(1),
  width: z.number().int().positive().max(7680).optional(),
  height: z.number().int().positive().max(4320).optional(),
  fps: z.number().int().positive().max(120).optional(),
  crf: z.number().int().min(0).max(51).optional(),
  durationSec: z.number().positive().optional(),
});

const cancelJobSchema = z.object({
  jobId: z.string().min(1),
});

export function registerFfmpegIpc(): void {
  ipcMain.handle("ffmpeg:available", async () => ok({ available: await checkFfmpeg() }));

  ipcMain.handle("ffmpeg:probe", async (_event, payload: unknown) => {
    try {
      const input = ffprobeSchema.parse(payload);
      return ok(await probe(input.path));
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("ffmpeg:run", (event, payload: unknown) => {
    try {
      const input = transcodeSchema.parse(payload);
      const jobId = runTranscode(input, {
        onProgress: (progress) => {
          if (!event.sender.isDestroyed()) event.sender.send("ffmpeg:progress", progress);
        },
        onDone: (output) => {
          if (!event.sender.isDestroyed()) event.sender.send("ffmpeg:done", { jobId, output });
        },
        onError: (message) => {
          if (!event.sender.isDestroyed()) event.sender.send("ffmpeg:failed", { jobId, message });
        },
      });
      return ok({ jobId });
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("ffmpeg:cancel", (_event, payload: unknown) => {
    try {
      const input = cancelJobSchema.parse(payload);
      return ok({ cancelled: cancelJob(input.jobId) });
    } catch (error) {
      return toError(error);
    }
  });
}
