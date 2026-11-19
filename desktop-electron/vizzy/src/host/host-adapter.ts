/**
 * CAMXORA host adapter, loaded after the editor.
 *
 * Responsibilities, in order of importance:
 *  1. Route the editor's own Save through the native project store when the
 *     desktop bridge is present (the IndexedDB path stays as the web fallback;
 *     `src/main.ts` has a one-line CAMXORA-PATCH hook for this).
 *  2. Apply projects the host opens through the native dialog.
 *  3. Report name / dirty / node count / FFT tier to the shell strip.
 *  4. Expose the read-only `window.__vizzyTest` snapshot the E2E harness reads.
 *
 * It never touches the renderer, the project model or the DOM structure of the
 * editor beyond the two status labels in the top bar.
 *
 * `scripts/sync-vizzy.mjs` copies this file to `src/host/host-adapter.ts`.
 */
import type {
  VizzyHostBridge,
  VizzyHostState,
  VizzyOpenedProject,
  VizzyProjectInfo,
} from "./bridge";

interface ProjectLike {
  name: string;
  nodes: unknown[];
  width?: number;
  height?: number;
  fps?: number;
  duration?: number;
}

interface HistoryLike {
  labels(): string[];
  onChange(listener: () => void): () => void;
  clear(): void;
}

interface EditorGlobals {
  editorProject?: ProjectLike;
  editorSpectrum?: { tier?: string };
  editHistory?: HistoryLike;
  editorSerializeProject?: () => unknown;
  editorRestoreProject?: (snapshot: unknown) => void;
}

export interface VizzyTestSnapshot {
  ready: boolean;
  projectName: string;
  dirty: boolean;
  nodeCount: number;
  projectWidth: number;
  projectHeight: number;
  projectFps: number;
  projectDuration: number;
  crossOriginIsolated: boolean;
  fftTier: string;
}

export interface VizzyTestApi extends VizzyTestSnapshot {
  /** Current project snapshot as JSON. Read-only: it does not mutate state. */
  readProjectJson(): string;
  /** Project defaults for the export popover (name, size, fps, duration). */
  readProjectInfo(): VizzyProjectInfo;
}

declare global {
  interface Window {
    camxoraVizzy?: VizzyHostBridge;
    __vizzyTest?: VizzyTestApi;
  }
}

const globals = globalThis as unknown as EditorGlobals;
const bridge = window.camxoraVizzy;

let ready = false;
let dirty = false;
/** History depth at the last save/open; a different depth means unsaved work. */
let savedLabelCount = 0;
let reportedKey = "";

function editorReady(): boolean {
  return Boolean(globals.editorProject && globals.editorSerializeProject && globals.editHistory);
}

function snapshot(): VizzyTestSnapshot {
  const info = readProjectInfo();
  return {
    ready,
    projectName: globals.editorProject?.name ?? "",
    dirty,
    nodeCount: globals.editorProject?.nodes.length ?? 0,
    projectWidth: info.width,
    projectHeight: info.height,
    projectFps: info.fps,
    projectDuration: info.duration,
    crossOriginIsolated: globalThis.crossOriginIsolated === true,
    fftTier: globals.editorSpectrum?.tier ?? "unknown",
  };
}

function readProjectJson(): string {
  const serialize = globals.editorSerializeProject;
  if (!serialize) throw new Error("The editor is not ready yet.");
  return JSON.stringify(serialize());
}

function readProjectInfo(): VizzyProjectInfo {
  const project = globals.editorProject;
  const number = (value: unknown): number =>
    typeof value === "number" && Number.isFinite(value) ? value : 0;
  return {
    name: project?.name ?? "",
    width: number(project?.width),
    height: number(project?.height),
    fps: number(project?.fps),
    duration: number(project?.duration),
  };
}

function reportState(): void {
  if (!bridge) return;
  const state = snapshot();
  const key = `${state.projectName}|${state.dirty}|${state.nodeCount}|${state.projectWidth}x${state.projectHeight}@${state.projectFps}|${state.projectDuration}|${state.fftTier}|${state.ready}`;
  if (key === reportedKey) return;
  reportedKey = key;
  const payload: VizzyHostState = {
    ready: state.ready,
    projectName: state.projectName,
    dirty: state.dirty,
    nodeCount: state.nodeCount,
    projectWidth: state.projectWidth,
    projectHeight: state.projectHeight,
    projectFps: state.projectFps,
    projectDuration: state.projectDuration,
    crossOriginIsolated: state.crossOriginIsolated,
    fftTier: state.fftTier,
  };
  bridge.reportState(payload);
}

function setDirty(next: boolean): void {
  if (dirty === next) return;
  dirty = next;
  bridge?.notifyDirty(next);
  reportState();
}

function paintSaveState(text: string): void {
  const element = document.getElementById("save-state");
  if (element) element.textContent = text;
}

function paintProjectName(name: string): void {
  const element = document.getElementById("project-name");
  if (element) element.textContent = name;
}

/** Treat the current history depth as saved. */
function markSaved(): void {
  savedLabelCount = globals.editHistory?.labels().length ?? 0;
  setDirty(false);
  reportState();
}

function watchHistory(): void {
  const history = globals.editHistory;
  if (!history) return;
  history.onChange(() => {
    const count = history.labels().length;
    if (count !== savedLabelCount) setDirty(true);
    else setDirty(false);
    reportState();
  });
}

function applyHostProject(project: VizzyOpenedProject, requestId: string): void {
  try {
    const restore = globals.editorRestoreProject;
    if (!restore) throw new Error("The editor is not ready yet.");
    const parsed = JSON.parse(project.json) as unknown;
    restore(parsed);
    paintProjectName(globals.editorProject?.name ?? project.name);
    paintSaveState(
      `Saved ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`,
    );
    // `applyProjectSnapshot` clears history; that is the new saved baseline.
    markSaved();
    bridge?.acknowledge({ requestId, ok: true });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    bridge?.acknowledge({ requestId, ok: false, error: message });
  }
}

function installTestApi(): void {
  const api: VizzyTestApi = {
    get ready() {
      return ready;
    },
    get projectName() {
      return globals.editorProject?.name ?? "";
    },
    get dirty() {
      return dirty;
    },
    get nodeCount() {
      return globals.editorProject?.nodes.length ?? 0;
    },
    get crossOriginIsolated() {
      return globalThis.crossOriginIsolated === true;
    },
    get fftTier() {
      return globals.editorSpectrum?.tier ?? "unknown";
    },
    readProjectJson,
    readProjectInfo,
  };

  Object.defineProperty(window, "__vizzyTest", {
    configurable: false,
    enumerable: true,
    writable: false,
    value: Object.freeze(api),
  });
}

function subscribeToHost(): void {
  if (!bridge) return;
  bridge.onCommand((command) => {
    if (command.type === "open-project") {
      applyHostProject(
        { path: command.path, name: command.name, json: command.json },
        command.requestId,
      );
      return;
    }
    if (command.type === "project-saved") {
      paintSaveState(
        `Saved ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`,
      );
      markSaved();
    }
  });
}

function begin(): void {
  if (!editorReady()) {
    window.setTimeout(begin, 50);
    return;
  }

  installTestApi();
  subscribeToHost();
  watchHistory();
  paintProjectName(globals.editorProject?.name ?? "");
  markSaved();

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      ready = true;
      reportState();
    });
  });
}

begin();
