import { logger } from "../services/logger";
import type { VizzyHost } from "../vizzy-host/host";
import { registerApiIpc } from "./api";
import { registerAuthIpc } from "./auth";
import { registerFfmpegIpc } from "./ffmpeg";
import { registerFilesIpc } from "./files";
import { registerPreferencesIpc } from "./preferences";
import { registerSystemIpc } from "./system";
import { registerUpdatesIpc } from "./updates";
import { registerTemplatesIpc } from "./templates";
import { registerVizzyIpc } from "./vizzy";

let registered = false;

export function registerIpc(vizzyHost: VizzyHost): void {
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
  registerVizzyIpc(vizzyHost);

  logger.info("ipc registered");
}
