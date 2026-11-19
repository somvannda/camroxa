import fs from "node:fs";
import path from "node:path";
import { app, BrowserWindow, protocol, session, shell } from "electron";
import { registerIpc } from "./ipc";
import { stopDownloadCoordinator } from "./ipc/downloads";
import { logger } from "./services/logger";
import { handleMediaRequest } from "./services/media";
import { ensureAppDirs, getAppPaths } from "./services/paths";
import { resolveLibraryRoot } from "./services/vizzy-library";
import { closeStore, initStore } from "./services/store";
import { APP_NAME, APP_VERSION, USER_DATA_FOLDER } from "./shared/version";
import { VizzyHost } from "./vizzy-host/host";
import { installVizzyProtocol, installVizzyProtocolForSession, registerHostSchemes } from "./vizzy-host/protocol";
import { VIZZY_RENDER_PARTITION } from "./vizzy-host/render-window";

// Privileged scheme registration must run before the app is ready; the handlers
// themselves are installed after `whenReady()`. One call registers both
// `camxora-media://` and `camxora-vizzy://` (Electron keeps a single list).
registerHostSchemes();

const isDev = Boolean(process.env.VITE_DEV_SERVER_URL);
let mainWindow: BrowserWindow | null = null;
let vizzyHost: VizzyHost | null = null;

/** `vizzy-dist/` next to the app bundle, or inside the packaged resources. */
function vizzyBundleRoot(): string {
  return app.isPackaged
    ? path.join(process.resourcesPath, "vizzy-dist")
    : path.join(__dirname, "..", "vizzy-dist");
}

/**
 * `vizzy-library/` from the staged pack. `resolveLibraryRoot()` honours
 * `CAMXORA_VIZZY_LIBRARY_DIR`, then packaged resources, then the app directory,
 * so the same code path serves dev, E2E and the installer.
 */
function vizzyLibraryRoot(): string | null {
  const root = resolveLibraryRoot();
  return fs.existsSync(path.join(root, "manifest.json")) ? root : null;
}

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

  window.once("ready-to-show", () => {
    window.show();
    window.focus();
  });

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
    vizzyHost?.dispose();
  });

  return window;
}

app.whenReady().then(() => {
  ensureAppDirs();
  initStore();
  protocol.handle("camxora-media", handleMediaRequest);

  const vizzyRoot = vizzyBundleRoot();
  const vizzyLibrary = vizzyLibraryRoot();
  try {
    installVizzyProtocol({
      root: vizzyRoot,
      libraryRoot: vizzyLibrary,
      onError: (error) => logger.error("vizzy protocol", { error: String(error) }),
    });
  } catch (error) {
    logger.error("vizzy bundle unavailable", { error: String(error), root: vizzyRoot });
  }

  // Protocol handlers are per session. The batch render window runs on a
  // dedicated partition, so it needs the same two handlers installed there.
  try {
    const renderSession = session.fromPartition(VIZZY_RENDER_PARTITION);
    renderSession.protocol.handle("camxora-media", handleMediaRequest);
    installVizzyProtocolForSession(renderSession, {
      root: vizzyRoot,
      libraryRoot: vizzyLibrary,
      onError: (error) => logger.error("vizzy render protocol", { error: String(error) }),
    });
  } catch (error) {
    logger.error("vizzy render session unavailable", { error: String(error), root: vizzyRoot });
  }

  vizzyHost = new VizzyHost({
    getWindow: () => mainWindow,
    preloadPath: path.join(__dirname, "vizzy-preload.cjs"),
    root: vizzyRoot,
    projectsDir: getAppPaths().projects,
    rendersDir: getAppPaths().renders,
    onState: (state) => {
      if (mainWindow && !mainWindow.webContents.isDestroyed()) {
        mainWindow.webContents.send("vizzy:state", state);
      }
    },
    onExportProgress: (progress) => {
      if (mainWindow && !mainWindow.webContents.isDestroyed()) {
        mainWindow.webContents.send("vizzy:export:progress", progress);
      }
    },
  });

  registerIpc(vizzyHost, { getWindow: () => mainWindow });

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
  // Abort live downloads and delete their partial files before the store closes.
  stopDownloadCoordinator();
  vizzyHost?.dispose();
  closeStore();
});

process.on("uncaughtException", (error) => {
  logger.error("uncaught exception", { error: String(error), stack: error.stack });
});
