/**
 * Custom-protocol transport for the hosted Vizzy page.
 *
 * Option A in the host spike: serve the editor from `camxora-vizzy://vizzy/…`
 * with COOP/COEP/CORP. The scheme must be registered as privileged *before*
 * `app.whenReady()`, and `protocol.handle` must be installed after it.
 *
 * All path/MIME/header logic lives in `assets.ts` so it can be tested without
 * Electron.
 */
import { protocol, type Session } from "electron";
import fs from "node:fs";
import path from "node:path";
import { mediaSchemePrivileges } from "../services/media";
import {
  VIZZY_HOST,
  VIZZY_SCHEME,
  resolveVizzyRequest,
  vizzyAssetStreamResponse,
  vizzyErrorResponse,
} from "./assets";

export interface VizzyProtocolOptions {
  /** Absolute directory that contains `index.html`. */
  root: string;
  /** Optional staged template library; `/creations/*` is served from here. */
  libraryRoot?: string | null;
  /** Optional hook for diagnostics; never used for auth. */
  onRequest?: (info: { pathname: string; status: number }) => void;
  /** Optional error sink (missing root, handler failure). */
  onError?: (error: Error) => void;
}

/**
 * Register the scheme. Call once, at module scope in the main process, before
 * the app is ready. `secure` is what makes the origin a secure context;
 * `standard` is what makes relative URLs, workers and module scripts resolve.
 *
 * NOTE: Electron keeps one privileged-scheme list per process — a second
 * `registerSchemesAsPrivileged` call replaces the first. The app therefore
 * registers `camxora-media://` and `camxora-vizzy://` together through
 * `registerHostSchemes()`. This single-scheme function remains for standalone
 * hosts such as `spike-main.ts`.
 */
export function registerVizzyScheme(): void {
  protocol.registerSchemesAsPrivileged([vizzySchemePrivileges()]);
}

export type PrivilegedScheme = Parameters<typeof protocol.registerSchemesAsPrivileged>[0][number];

export function vizzySchemePrivileges(): PrivilegedScheme {
  return {
    scheme: VIZZY_SCHEME,
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      stream: true,
      corsEnabled: true,
      codeCache: true,
    },
  };
}

/**
 * Register every custom scheme the desktop app serves. Must run before
 * `app.whenReady()`, once per process.
 */
export function registerHostSchemes(): void {
  protocol.registerSchemesAsPrivileged([mediaSchemePrivileges(), vizzySchemePrivileges()]);
}

export function createVizzyProtocolHandler(
  options: VizzyProtocolOptions,
): (request: Request) => Promise<Response> {
  const root = path.resolve(options.root);
  const libraryRoot = options.libraryRoot ? path.resolve(options.libraryRoot) : null;

  return async (request: Request): Promise<Response> => {
    try {
      let url: URL;
      try {
        url = new URL(request.url);
      } catch {
        options.onRequest?.({ pathname: "", status: 400 });
        return vizzyErrorResponse(400, "Bad request");
      }

      if (url.hostname !== VIZZY_HOST) {
        options.onRequest?.({ pathname: url.pathname, status: 404 });
        return vizzyErrorResponse(404, "Not found");
      }

      if (request.method !== "GET" && request.method !== "HEAD") {
        options.onRequest?.({ pathname: url.pathname, status: 405 });
        return vizzyErrorResponse(405, "Method not allowed");
      }

      const lookup = resolveVizzyRequest(root, libraryRoot, url.pathname);
      if (!lookup.ok) {
        options.onRequest?.({ pathname: url.pathname, status: lookup.status });
        return vizzyErrorResponse(lookup.status, lookup.message);
      }

      options.onRequest?.({ pathname: url.pathname, status: 200 });
      return vizzyAssetStreamResponse(
        lookup.asset,
        request.headers.get("range"),
        request.method,
      );
    } catch (error) {
      const failure = error instanceof Error ? error : new Error(String(error));
      options.onError?.(failure);
      return vizzyErrorResponse(500, "Vizzy asset failed");
    }
  };
}

let installed = false;

/**
 * Install the handler. Must run after `app.whenReady()` resolves, and only once
 * per process: re-registering a scheme logs a warning and replaces the handler.
 *
 * Throws when the bundle is missing so a packaging error surfaces at startup
 * instead of as a blank editor.
 */
export function installVizzyProtocol(options: VizzyProtocolOptions): void {
  const root = path.resolve(options.root);
  const index = path.join(root, "index.html");
  if (!fs.existsSync(index)) {
    throw new Error(
      `Vizzy bundle missing: ${index}. Run "npm run vizzy:build" in desktop-electron/.`,
    );
  }
  if (installed) return;
  installed = true;
  protocol.handle(VIZZY_SCHEME, createVizzyProtocolHandler({ ...options, root }));
}

/**
 * Install the handler on an explicit session (Electron keeps protocol handlers
 * per session, not per app). The batch render window runs on its own partition,
 * so it needs its own `camxora-vizzy://` handler.
 */
export function installVizzyProtocolForSession(
  target: Session,
  options: VizzyProtocolOptions,
): void {
  const root = path.resolve(options.root);
  const index = path.join(root, "index.html");
  if (!fs.existsSync(index)) {
    throw new Error(
      `Vizzy bundle missing: ${index}. Run "npm run vizzy:build" in desktop-electron/.`,
    );
  }
  target.protocol.handle(VIZZY_SCHEME, createVizzyProtocolHandler({ ...options, root }));
}
