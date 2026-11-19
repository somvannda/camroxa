/**
 * Vizzy host view — the container the real editor will live in.
 *
 * This is the same shape as the P7 design: a `WebContentsView` owned by the
 * shell window, sandboxed, with no preload in the spike. The spike only adds
 * measurement plumbing; it is not imported by `electron/main.ts`.
 */
import { BrowserWindow, WebContentsView, shell, type WebContents } from "electron";

export type VizzySpikeMode = "protocol" | "loopback";

export interface VizzyHostBounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface VizzySpikeResult {
  ok: boolean;
  crossOriginIsolated: boolean;
  sharedArrayBuffer: boolean;
  sharedMemoryWorks: boolean;
  required?: Record<string, boolean>;
  fatal?: string;
  [key: string]: unknown;
}

export interface VizzySpikeEnvelope {
  status: "running" | "done" | "error";
  mode: VizzySpikeMode;
  url: string;
  pageRoot: string;
  startedAt: number;
  elapsedMs: number;
  versions: { electron: string; chrome: string; node: string };
  platform: string;
  result?: VizzySpikeResult | null;
  probeError?: string | null;
  title?: string;
}

export interface VizzyHostViewOptions {
  url: string;
  bounds?: VizzyHostBounds;
  /** Only used once the bridge exists; the spike runs without a preload. */
  preloadPath?: string;
  onCrash?: (details: { reason: string; exitCode: number }) => void;
  onConsoleError?: (message: string) => void;
}

const DEFAULT_BOUNDS: VizzyHostBounds = { x: 0, y: 0, width: 1280, height: 800 };

export function createVizzyHostView(options: VizzyHostViewOptions): WebContentsView {
  const view = new WebContentsView({
    webPreferences: {
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      webSecurity: true,
      spellcheck: false,
      backgroundThrottling: false,
      ...(options.preloadPath ? { preload: options.preloadPath } : {}),
    },
  });

  view.setBounds(options.bounds ?? DEFAULT_BOUNDS);
  const contents = view.webContents;
  const hostPrefix = (() => {
    try {
      const parsed = new URL(options.url);
      return `${parsed.protocol}//${parsed.host}`;
    } catch {
      return options.url;
    }
  })();

  contents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url)) void shell.openExternal(url);
    return { action: "deny" };
  });

  contents.on("will-navigate", (event, url) => {
    // The editor never navigates away from its own host origin.
    if (url !== options.url && !url.startsWith(hostPrefix)) {
      event.preventDefault();
      if (/^https?:\/\//i.test(url)) void shell.openExternal(url);
    }
  });

  contents.on("render-process-gone", (_event, details) => {
    options.onCrash?.({ reason: details.reason, exitCode: details.exitCode });
  });

  contents.on("console-message", (_event, level, message) => {
    if (level >= 2) options.onConsoleError?.(message);
  });

  return view;
}

export interface VizzyHostWindowOptions {
  url: string;
  bounds?: VizzyHostBounds;
  title?: string;
  onCrash?: (details: { reason: string; exitCode: number }) => void;
}

/**
 * Standalone shell window used by the spike. The production host attaches the
 * view to the existing shell window instead of creating a second BrowserWindow.
 */
export function createVizzyHostWindow(options: VizzyHostWindowOptions): {
  window: BrowserWindow;
  view: WebContentsView;
} {
  const bounds = options.bounds ?? DEFAULT_BOUNDS;
  const window = new BrowserWindow({
    width: bounds.width,
    height: bounds.height,
    show: true,
    backgroundColor: "#0b0d10",
    title: options.title ?? "Vizzy host spike",
    webPreferences: {
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  });

  const view = createVizzyHostView({ url: options.url, bounds: { ...bounds, x: 0, y: 0 }, onCrash: options.onCrash });
  window.contentView.addChildView(view);

  const syncBounds = (): void => {
    const { width, height } = window.getContentBounds();
    view.setBounds({ x: 0, y: 0, width, height });
  };
  window.on("resize", syncBounds);
  syncBounds();

  return { window, view };
}

/**
 * Poll the page for its published probe result. `executeJavaScript` is the same
 * hook the P7 E2E harness will use to read `window.__vizzyTest`, so this also
 * proves the measurement path works through a `WebContentsView`.
 */
export async function waitForVizzySpikeResult(
  contents: WebContents,
  timeoutMs = 20000,
  intervalMs = 150,
): Promise<VizzySpikeResult | null> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const value: unknown = await contents.executeJavaScript(
        "window.__vizzySpikeResult ?? null",
        true,
      );
      if (value && typeof value === "object") return value as VizzySpikeResult;
    } catch {
      // The document is still loading or the frame was replaced; retry.
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  return null;
}
