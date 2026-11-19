/**
 * Tokenised loopback transport for the hosted Vizzy page.
 *
 * Option B in the host spike: serve the same page from
 * `http://127.0.0.1:<random>/t/<token>/` with the identical isolation headers.
 *
 * Rules the real host must keep if this transport is chosen:
 * - bind to 127.0.0.1 only, never 0.0.0.0;
 * - pick an ephemeral port (0), never a fixed one;
 * - require an unguessable path token on every request, including assets;
 * - reject all methods except GET/HEAD;
 * - never serve a path outside `root`;
 * - stop the server when the view closes.
 */
import fs from "node:fs";
import http from "node:http";
import type { AddressInfo } from "node:net";
import path from "node:path";
import { randomBytes } from "node:crypto";
import {
  VIZZY_INDEX_PATH,
  resolveVizzyAsset,
  vizzyErrorResponse,
  vizzyResponseHeaders,
} from "./assets";

export interface VizzyLoopbackServer {
  origin: string;
  token: string;
  /** Full page URL, including the token prefix. */
  pageUrl: string;
  close(): Promise<void>;
}

export interface VizzyLoopbackOptions {
  root: string;
  /** Test hook only; production must leave this undefined. */
  token?: string;
  host?: string;
}

function writeResponse(res: http.ServerResponse, response: Response): void {
  res.writeHead(response.status, Object.fromEntries(response.headers.entries()));
}

export async function startVizzyLoopbackServer(
  options: VizzyLoopbackOptions,
): Promise<VizzyLoopbackServer> {
  const root = path.resolve(options.root);
  const host = options.host ?? "127.0.0.1";
  const token = options.token ?? randomBytes(16).toString("hex");
  const prefix = `/t/${token}`;

  const server = http.createServer(async (req, res) => {
    try {
      if (req.method !== "GET" && req.method !== "HEAD") {
        writeResponse(res, vizzyErrorResponse(405, "Method not allowed"));
        res.end();
        return;
      }

      const requestUrl = new URL(req.url ?? "/", `http://${host}`);
      if (requestUrl.pathname !== prefix && !requestUrl.pathname.startsWith(`${prefix}/`)) {
        // No token, wrong token, or probing another path: do not reveal that a
        // server exists beyond a bare 404.
        writeResponse(res, vizzyErrorResponse(404, "Not found"));
        res.end();
        return;
      }

      const relative = requestUrl.pathname.slice(prefix.length);
      const lookup = resolveVizzyAsset(root, relative === "" ? `/${VIZZY_INDEX_PATH}` : relative);
      if (!lookup.ok) {
        writeResponse(res, vizzyErrorResponse(lookup.status, lookup.message));
        res.end();
        return;
      }

      const response = vizzyResponseHeaders(lookup.asset.mime);
      if (req.method === "HEAD") {
        res.writeHead(200, { ...response, "Content-Length": String(lookup.asset.size) });
        res.end();
        return;
      }

      const { readFileSync } = fs;
      const body = readFileSync(lookup.asset.filePath);
      res.writeHead(200, { ...response, "Content-Length": String(body.byteLength) });
      res.end(body);
    } catch {
      if (!res.headersSent) writeResponse(res, vizzyErrorResponse(500, "Server error"));
      res.end();
    }
  });

  await new Promise<void>((resolve, reject) => {
    const onError = (error: Error): void => reject(error);
    server.once("error", onError);
    server.listen(0, host, () => {
      server.off("error", onError);
      resolve();
    });
  });

  const address = server.address() as AddressInfo;
  const origin = `http://${host}:${address.port}`;

  return {
    origin,
    token,
    pageUrl: `${origin}${prefix}/${VIZZY_INDEX_PATH}`,
    close: () =>
      new Promise<void>((resolve, reject) => {
        server.close((error) => (error ? reject(error) : resolve()));
      }),
  };
}
