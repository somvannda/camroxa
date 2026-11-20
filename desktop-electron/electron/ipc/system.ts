import { app, BrowserWindow, ipcMain } from "electron";
import { logger } from "../services/logger";
import { devAuthBypass } from "../shared/flags";
import { ok, type AppInfo } from "../shared/types";
import { APP_NAME, APP_VERSION } from "../shared/version";

export function registerSystemIpc(): void {
  ipcMain.handle("app:info", (): AppInfo => {
    const apiBaseUrl =
      process.env.CAMXORA_API_BASE_URL?.replace(/\/+$/, "") ??
      "http://127.0.0.1:8000/api/v1";
    const env =
      process.env.CAMXORA_BUILD_ENV ??
      (/sandbox/i.test(apiBaseUrl)
        ? "sandbox"
        : /localhost|127\.0\.0\.1/i.test(apiBaseUrl)
          ? "local"
          : /(^|\.)api\.camxora\.com/i.test(apiBaseUrl)
            ? "production"
            : "development");
    return {
      name: APP_NAME,
      version: APP_VERSION,
      env,
      platform: process.platform,
      electron: process.versions.electron ?? "",
      chrome: process.versions.chrome ?? "",
      node: process.versions.node ?? "",
      devBypass: devAuthBypass(),
      portalUrl: process.env.CAMXORA_PORTAL_BASE_URL ?? "https://app.camxora.com",
      build: process.env.CAMXORA_BUILD_ID ?? (app.isPackaged ? "release" : "dev"),
      apiBaseUrl,
    };
  });

  ipcMain.handle("window:minimize", (event) => {
    BrowserWindow.fromWebContents(event.sender)?.minimize();
  });

  ipcMain.handle("window:toggle-maximize", (event) => {
    const window = BrowserWindow.fromWebContents(event.sender);
    if (!window) return;
    if (window.isMaximized()) window.unmaximize();
    else window.maximize();
  });

  ipcMain.handle("window:close", (event) => {
    BrowserWindow.fromWebContents(event.sender)?.close();
  });

  ipcMain.handle("diagnostics:send", () => {
    const uploadId = `local-${Date.now().toString(36)}`;
    logger.info("diagnostics requested", { uploadId });
    return ok({ uploadId });
  });
}
