import { logger } from "../services/logger";
import type { VizzyHost } from "../vizzy-host/host";
import type { BrowserWindow } from "electron";
import { registerApiIpc } from "./api";
import { registerAuthIpc } from "./auth";
import { registerFfmpegIpc } from "./ffmpeg";
import { registerFilesIpc } from "./files";
import { registerPipelineIpc } from "./pipeline";
import { registerPreferencesIpc } from "./preferences";
import { registerSystemIpc } from "./system";
import { registerUpdatesIpc } from "./updates";
import { registerTemplatesIpc } from "./templates";
import { registerVideoTemplatesIpc } from "./video-templates";
import { registerVizzyIpc } from "./vizzy";

let registered = false;

export interface IpcWindowOptions {
  /** The shell window that owns the durable pipeline queue. */
  getWindow: () => BrowserWindow | null;
}

export function registerIpc(vizzyHost: VizzyHost, options?: IpcWindowOptions): void {
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
  registerVideoTemplatesIpc();
  registerVizzyIpc(vizzyHost);
  if (options) registerPipelineIpc({ host: vizzyHost, getWindow: options.getWindow });

  logger.info("ipc registered");
}
