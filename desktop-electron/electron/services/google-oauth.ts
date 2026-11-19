import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";

export const DEFAULT_LOOPBACK_PORT = 41580;
export const CALLBACK_PATH = "/google/callback";
export const LOOPBACK_HOST = "127.0.0.1";
export const DEFAULT_WAIT_TIMEOUT_MS = 300_000;

export type GoogleOAuthErrorCode =
  | "OAUTH_PORT_BUSY"
  | "OAUTH_TIMEOUT"
  | "OAUTH_CANCELLED"
  | "OAUTH_ERROR"
  | "OAUTH_IN_PROGRESS";

export class GoogleOAuthError extends Error {
  constructor(
    public readonly code: GoogleOAuthErrorCode,
    message: string,
  ) {
    super(message);
    this.name = "GoogleOAuthError";
  }
}

export interface GoogleCallback {
  code: string;
  state: string;
}

const PAGE_STYLE =
  "margin:0;min-height:100vh;display:grid;place-items:center;background:#0b0d10;" +
  "color:#f5f6f7;font-family:Inter,'Segoe UI',system-ui,sans-serif";

function page(title: string, heading: string, body: string, accent: string): string {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8">` +
    `<title>${title}</title></head>` +
    `<body style="${PAGE_STYLE}"><main style="max-width:420px;padding:32px 36px;` +
    `border-radius:12px;background:#12161c;border:1px solid ${accent};text-align:center">` +
    `<h1 style="margin:0 0 8px;font-size:20px;font-weight:600">${heading}</h1>` +
    `<p style="margin:0;color:#9aa4b2;font-size:14px;line-height:1.6">${body}</p>` +
    `</main></body></html>`;
}

const SUCCESS_PAGE = page(
  "CAMXORA - signed in",
  "You're signed in",
  "Return to the CAMXORA studio. You can close this tab.",
  "rgba(88,166,255,0.35)",
);

const FAILURE_PAGE = page(
  "CAMXORA - sign-in not completed",
  "Sign-in was not completed",
  "Return to the CAMXORA studio and try again.",
  "rgba(248,113,113,0.35)",
);

export function loopbackPortFromEnv(): number {
  const raw = (process.env.CAMXORA_OAUTH_LOOPBACK_PORT ?? "").trim();
  if (!raw) return DEFAULT_LOOPBACK_PORT;
  const port = Number(raw);
  if (!Number.isInteger(port) || port < 1 || port > 65535) return DEFAULT_LOOPBACK_PORT;
  return port;
}

function respond(response: ServerResponse, status: number, html: string): void {
  const body = Buffer.from(html, "utf8");
  response.writeHead(status, {
    "Content-Type": "text/html; charset=utf-8",
    "Content-Length": body.byteLength,
    "Cache-Control": "no-store",
    Connection: "close",
  });
  response.end(body);
}

/**
 * One-shot loopback listener for the Google redirect.
 *
 * The server binds 127.0.0.1 only (never 0.0.0.0), accepts exactly one callback,
 * and is closed as soon as the flow settles or is cancelled.
 */
export class GoogleLoopbackServer {
  private readonly requestedPort: number;
  private server: Server | null = null;
  private boundPort: number | null = null;
  private settled = false;
  private resolveOutcome: ((value: GoogleCallback) => void) | null = null;
  private rejectOutcome: ((reason: Error) => void) | null = null;
  private readonly outcome: Promise<GoogleCallback>;

  constructor(port: number = loopbackPortFromEnv()) {
    this.requestedPort = port;
    this.outcome = new Promise<GoogleCallback>((resolve, reject) => {
      this.resolveOutcome = resolve;
      this.rejectOutcome = reject;
    });
    // The flow can be cancelled before anything awaits `wait()`.
    void this.outcome.catch(() => undefined);
  }

  get port(): number {
    return this.boundPort ?? this.requestedPort;
  }

  get redirectUri(): string {
    return `http://${LOOPBACK_HOST}:${this.port}${CALLBACK_PATH}`;
  }

  async start(): Promise<string> {
    if (this.server) return this.redirectUri;

    const server = createServer((request, response) => this.handle(request, response));
    await new Promise<void>((resolve, reject) => {
      const onError = () => {
        server.removeListener("listening", onListening);
        reject(
          new GoogleOAuthError(
            "OAUTH_PORT_BUSY",
            `Port ${this.requestedPort} is busy. Close the other CAMXORA window and try again.`,
          ),
        );
      };
      const onListening = () => {
        server.removeListener("error", onError);
        resolve();
      };
      server.once("error", onError);
      server.once("listening", onListening);
      server.listen(this.requestedPort, LOOPBACK_HOST);
    });

    const address = server.address();
    this.boundPort =
      typeof address === "object" && address !== null ? address.port : this.requestedPort;
    this.server = server;
    return this.redirectUri;
  }

  wait(timeoutMs: number = DEFAULT_WAIT_TIMEOUT_MS): Promise<GoogleCallback> {
    return new Promise<GoogleCallback>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.settle(
          new GoogleOAuthError(
            "OAUTH_TIMEOUT",
            "Google sign-in timed out. Please try again.",
          ),
        );
        this.close();
      }, timeoutMs);

      void this.outcome.then(
        (value) => {
          clearTimeout(timer);
          resolve(value);
        },
        (error: unknown) => {
          clearTimeout(timer);
          reject(error);
        },
      );
    });
  }

  cancel(message = "Google sign-in was cancelled."): void {
    this.settle(new GoogleOAuthError("OAUTH_CANCELLED", message));
    this.close();
  }

  close(): void {
    const server = this.server;
    this.server = null;
    if (!server) return;
    try {
      server.close();
    } catch {
      // Nothing else to release.
    }
  }

  private settle(error: Error | null, value?: GoogleCallback): void {
    if (this.settled) return;
    this.settled = true;
    if (error) {
      this.rejectOutcome?.(error);
      return;
    }
    if (value) this.resolveOutcome?.(value);
  }

  private handle(request: IncomingMessage, response: ServerResponse): void {
    if (request.method !== "GET") {
      respond(response, 405, FAILURE_PAGE);
      return;
    }

    let url: URL;
    try {
      url = new URL(request.url ?? "/", this.redirectUri);
    } catch {
      respond(response, 400, FAILURE_PAGE);
      return;
    }

    if (url.pathname !== CALLBACK_PATH) {
      respond(response, 404, FAILURE_PAGE);
      return;
    }

    const error = url.searchParams.get("error");
    const code = url.searchParams.get("code") ?? "";
    const state = url.searchParams.get("state") ?? "";

    if (error) {
      respond(response, 200, FAILURE_PAGE);
      this.settle(
        new GoogleOAuthError(
          error === "access_denied" ? "OAUTH_CANCELLED" : "OAUTH_ERROR",
          error === "access_denied"
            ? "Google sign-in was cancelled."
            : "Google sign-in failed. Please try again.",
        ),
      );
      this.close();
      return;
    }

    if (!code || !state) {
      respond(response, 200, FAILURE_PAGE);
      this.settle(
        new GoogleOAuthError(
          "OAUTH_ERROR",
          "Google did not return an authorization code. Please try again.",
        ),
      );
      this.close();
      return;
    }

    respond(response, 200, SUCCESS_PAGE);
    this.settle(null, { code, state });
    this.close();
  }
}
