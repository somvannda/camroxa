import path from "node:path";
import { app, BrowserWindow, protocol, session, shell } from "electron";
import { registerIpc } from "./ipc";
import { logger } from "./services/logger";
import { handleMediaRequest, registerMediaScheme } from "./services/media";
import { ensureAppDirs } from "./services/paths";
import { closeStore, initStore } from "./services/store";
import { APP_NAME, APP_VERSION, USER_DATA_FOLDER } from "./shared/version";

registerMediaScheme();

const isDev = Boolean(process.env.VITE_DEV_SERVER_URL);
let mainWindow: BrowserWindow | null = null;

app.setName(APP_NAME);
app.setAppUserModelId("com.camxora.desktop");
// Keep the Electron client isolated from the legacy PySide6 data in %APPDATA%\Camxora.
app.setPath(
  "userData",
  process.env.CAMXORA_USER_DATA_DIR
    ? path.resolve(process.env.CAMXORA_USER_DATA_DIR)
    : path.join(app.getPath("appData"), USER_DATA_FOLDER),
);

const singleInstance = app.requestSingleInstanceLock();
if (!singleInstance) {
  app.quit();
}

function createWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1280,
    minHeight: 800,
    show: false,
    frame: false,
    backgroundColor: "#070a13",
    title: "Camxora Desktop 2.0",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      devTools: isDev || process.env.CAMXORA_DEVTOOLS === "1",
    },
  });

  window.once("ready-to-show", () => window.show());

  window.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url)) void shell.openExternal(url);
    return { action: "deny" };
  });

  window.webContents.on("will-navigate", (event, url) => {
    const allowed = process.env.VITE_DEV_SERVER_URL;
    if (allowed && url.startsWith(allowed)) return;
    event.preventDefault();
    if (/^https?:\/\//i.test(url)) void shell.openExternal(url);
  });

  window.webContents.on("did-fail-load", (_event, code, description, url) => {
    logger.error("renderer load failed", { code, description, url });
  });

  window.webContents.on("console-message", (_event, level, message, line, sourceId) => {
    if (level >= 2) logger.warn("renderer console", { level, message, line, sourceId });
  });

  if (process.env.VITE_DEV_SERVER_URL) {
    void window.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    void window.loadFile(path.join(__dirname, "../dist/index.html"));
  }

  window.on("closed", () => {
    if (mainWindow === window) mainWindow = null;
  });

  return window;
}

app.whenReady().then(() => {
  ensureAppDirs();
  initStore();
  protocol.handle("camxora-media", handleMediaRequest);
  registerIpc();

  session.defaultSession.setPermissionRequestHandler((_webContents, permission, callback) => {
    callback(permission === "notifications");
  });

  mainWindow = createWindow();
  logger.info("app ready", { version: APP_VERSION, platform: process.platform });

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      mainWindow = createWindow();
    }
  });
});

app.on("second-instance", () => {
  if (!mainWindow) return;
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.focus();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  closeStore();
});

process.on("uncaughtException", (error) => {
  logger.error("uncaught exception", { error: String(error), stack: error.stack });
});
