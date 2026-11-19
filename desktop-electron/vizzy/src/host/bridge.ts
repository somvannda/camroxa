/**
 * CAMXORA host bridge contract for the hosted editor.
 *
 * `electron/vizzy-preload.ts` injects this object as `window.camxoraVizzy` in the
 * Vizzy `WebContentsView`. It is the only native surface the editor can reach:
 * no Node module, no `ipcRenderer`, no shell bridge (`window.camxora`).
 *
 * `scripts/sync-vizzy.mjs` copies this file to `src/host/bridge.ts`; edit the
 * copy under `vizzy/patches/`, never the generated one.
 */

export interface VizzyHostState {
  ready: boolean;
  projectName: string;
  dirty: boolean;
  nodeCount: number;
  crossOriginIsolated: boolean;
  fftTier: string;
}

export interface VizzySavedProject {
  path: string;
  name: string;
}

export interface VizzyOpenedProject {
  path: string;
  name: string;
  json: string;
}

/** host -> view commands. */
export type VizzyHostCommand =
  | {
      v: 1;
      type: "open-project";
      requestId: string;
      path: string;
      name: string;
      json: string;
    }
  | { v: 1; type: "project-saved"; path: string; name: string }
  | { v: 1; type: "request-reload" };

export interface VizzyHostBridge {
  readonly version: 1;
  readonly platform: "camxora-desktop";
  /** Persist the current project snapshot through the native project store. */
  saveProject(name: string, json: string): Promise<VizzySavedProject | null>;
  /** Ask the host for the native Open dialog and apply the picked project. */
  openProject(): Promise<VizzyOpenedProject | null>;
  /** Save-state strip: the editor reports its own dirty flag. */
  notifyDirty(dirty: boolean): void;
  /** Shell strip: name, dirty flag, node count and FFT tier. */
  reportState(state: VizzyHostState): void;
  /** Acknowledge an `open-project` command after it has been applied. */
  acknowledge(payload: { requestId: string; ok: boolean; error?: string }): void;
  onCommand(handler: (command: VizzyHostCommand) => void): () => void;
}
