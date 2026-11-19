/**
 * Dedicated preload for the hosted Vizzy editor.
 *
 * The view runs with `contextIsolation: true`, `sandbox: true` and
 * `nodeIntegration: false`. This file injects exactly one object —
 * `window.camxoraVizzy` — and nothing else: no `ipcRenderer`, no `fs`, no shell
 * bridge. Every channel it touches is validated on the main side against the
 * view's own webContents id.
 *
 * Contract: `vizzy/patches/bridge.ts` (vendored into `vizzy/src/host/bridge.ts`).
 */
import { contextBridge, ipcRenderer } from "electron";

const BRIDGE_CHANNEL = "vizzy:bridge";

interface VizzyHostState {
  ready: boolean;
  projectName: string;
  dirty: boolean;
  nodeCount: number;
  crossOriginIsolated: boolean;
  fftTier: string;
}

interface VizzySavedProject {
  path: string;
  name: string;
}

interface VizzyOpenedProject {
  path: string;
  name: string;
  json: string;
}

type VizzyHostCommand =
  | {
      v: 1;
      type: "open-project";
      requestId: string;
      path: string;
      name: string;
      json: string;
    }
  | { v: 1; type: "project-saved"; path: string; name: string };

interface HostMessage {
  v?: number;
  type?: string;
  requestId?: string;
  path?: string;
  name?: string;
  json?: string;
}

function toCommand(message: HostMessage): VizzyHostCommand | null {
  if (message.v !== 1) return null;
  if (message.type === "vizzy:open-project-json") {
    if (
      typeof message.requestId !== "string" ||
      typeof message.path !== "string" ||
      typeof message.name !== "string" ||
      typeof message.json !== "string"
    ) {
      return null;
    }
    return {
      v: 1,
      type: "open-project",
      requestId: message.requestId,
      path: message.path,
      name: message.name,
      json: message.json,
    };
  }
  if (message.type === "vizzy:project-saved" && typeof message.path === "string") {
    return { v: 1, type: "project-saved", path: message.path, name: "" };
  }
  return null;
}

const bridge = {
  version: 1 as const,
  platform: "camxora-desktop" as const,

  saveProject(name: string, json: string): Promise<VizzySavedProject | null> {
    return ipcRenderer.invoke("vizzy:project:save", { name, json }) as Promise<VizzySavedProject | null>;
  },

  openProject(): Promise<VizzyOpenedProject | null> {
    return ipcRenderer.invoke("vizzy:project:open") as Promise<VizzyOpenedProject | null>;
  },

  notifyDirty(dirty: boolean): void {
    ipcRenderer.send(BRIDGE_CHANNEL, { v: 1, type: "vizzy:dirty", dirty: dirty === true });
  },

  reportState(state: VizzyHostState): void {
    ipcRenderer.send(BRIDGE_CHANNEL, { v: 1, type: "vizzy:state", state });
  },

  acknowledge(payload: { requestId: string; ok: boolean; error?: string }): void {
    ipcRenderer.send(BRIDGE_CHANNEL, {
      v: 1,
      type: "vizzy:ack",
      requestId: payload.requestId,
      ok: payload.ok === true,
      ...(payload.error ? { error: payload.error } : {}),
    });
  },

  onCommand(handler: (command: VizzyHostCommand) => void): () => void {
    const listener = (_event: unknown, message: HostMessage) => {
      const command = toCommand(message ?? {});
      if (command) handler(command);
    };
    ipcRenderer.on(BRIDGE_CHANNEL, listener);
    return () => {
      ipcRenderer.removeListener(BRIDGE_CHANNEL, listener);
    };
  },
};

contextBridge.exposeInMainWorld("camxoraVizzy", bridge);
