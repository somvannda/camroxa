import { logger } from "../services/logger";
import { registerApiIpc } from "./api";
import { registerAuthIpc } from "./auth";
import { registerFfmpegIpc } from "./ffmpeg";
import { registerFilesIpc } from "./files";
import { registerSystemIpc } from "./system";
import { registerTemplatesIpc } from "./templates";

let registered = false;

export function registerIpc(): void {
  if (registered) return;
  registered = true;

  registerSystemIpc();
  registerAuthIpc();
  registerApiIpc();
  registerFilesIpc();
  registerFfmpegIpc();
  registerTemplatesIpc();

  logger.info("ipc registered");
}
