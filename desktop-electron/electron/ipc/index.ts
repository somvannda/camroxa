import { logger } from "../services/logger";
import { registerApiIpc } from "./api";
import { registerAuthIpc } from "./auth";
import { registerFfmpegIpc } from "./ffmpeg";
import { registerFilesIpc } from "./files";
import { registerPreferencesIpc } from "./preferences";
import { registerSystemIpc } from "./system";
import { registerUpdatesIpc } from "./updates";
import { registerTemplatesIpc } from "./templates";

let registered = false;

export function registerIpc(): void {
  if (registered) return;
  registered = true;

  registerSystemIpc();
  registerAuthIpc();
  registerApiIpc();
  registerFilesIpc();
  registerPreferencesIpc();
  registerFfmpegIpc();
  registerUpdatesIpc();
  registerTemplatesIpc();

  logger.info("ipc registered");
}
