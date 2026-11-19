import { logger } from "../services/logger";
import { registerApiIpc } from "./api";
import { registerAuthIpc } from "./auth";
import { registerFfmpegIpc } from "./ffmpeg";
import { registerFilesIpc } from "./files";
import { registerSystemIpc } from "./system";

let registered = false;

export function registerIpc(): void {
  if (registered) return;
  registered = true;

  registerSystemIpc();
  registerAuthIpc();
  registerApiIpc();
  registerFilesIpc();
  registerFfmpegIpc();

  logger.info("ipc registered");
}
