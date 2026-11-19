/**
 * Custom-protocol transport for the hosted Vizzy page.
 *
 * Option A in the host spike: serve the editor from `camxora-vizzy://vizzy/…`
 * with COOP/COEP/CORP. The scheme must be registered as privileged *before*
 * `app.whenReady()`, and `protocol.handle` must be installed after it.
 *
 * This file is intentionally small: all path/MIME/header logic lives in
 * `assets.ts` so it can be tested without Electron.
 */
import { protocol } from "electron";
import path from "node:path";
import {
  VIZZY_HOST,
  VIZZY_SCHEME,
  resolveVizzyAsset,
  vizzyAssetResponse,
  vizzyErrorResponse,
} from "./assets";

export interface VizzyProtocolOptions {
  /** Absolute directory that contains `index.html`. */
  root: string;
  /** Optional hook for diagnostics; never used for auth. */
  onRequest?: (info: { pathname: string; status: number }) => void;
}

/**
 * Register the scheme. Call once, at module scope in the main process, before
 * the app is ready. `secure` is what makes the origin a secure context;
 * `standard` is what makes relative URLs, workers and module scripts resolve.
 */
export function registerVizzyScheme(): void {
  protocol.registerSchemesAsPrivileged([
    {
      scheme: VIZZY_SCHEME,
      privileges: {
        standard: true,
        secure: true,
        supportFetchAPI: true,
        stream: true,
        corsEnabled: true,
        codeCache: true,
      },
    },
  ]);
}

export function createVizzyProtocolHandler(
  options: VizzyProtocolOptions,
): (request: Request) => Promise<Response> {
  const root = path.resolve(options.root);

  return async (request: Request): Promise<Response> => {
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

    const lookup = resolveVizzyAsset(root, url.pathname);
    if (!lookup.ok) {
      options.onRequest?.({ pathname: url.pathname, status: lookup.status });
      return vizzyErrorResponse(lookup.status, lookup.message);
    }

    options.onRequest?.({ pathname: url.pathname, status: 200 });
    const response = vizzyAssetResponse(lookup.asset);
    if (request.method === "HEAD") {
      return new Response(null, { status: 200, headers: response.headers });
    }
    return response;
  };
}

/** Install the handler. Must run after `app.whenReady()` resolves. */
export function installVizzyProtocol(options: VizzyProtocolOptions): void {
  protocol.handle(VIZZY_SCHEME, createVizzyProtocolHandler(options));
}
