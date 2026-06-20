import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";

export type NgrokStatus = {
  running: boolean;
  publicUrl: string | null;
  callbackUrl: string | null;
  localPort: number | null;
  lastError: string | null;
};

export type NgrokManager = {
  status: () => NgrokStatus;
  start: (opts: { ngrokPath?: string; localPort: number; callbackPath?: string }) => Promise<NgrokStatus>;
  stop: () => Promise<NgrokStatus>;
};

function parseJsonLine(line: string) {
  try {
    return JSON.parse(line) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function createNgrokManager(): NgrokManager {
  let proc: ChildProcessWithoutNullStreams | null = null;
  let publicUrl: string | null = null;
  let callbackUrl: string | null = null;
  let localPort: number | null = null;
  let lastError: string | null = null;

  const status = (): NgrokStatus => ({
    running: Boolean(proc && !proc.killed),
    publicUrl,
    callbackUrl,
    localPort,
    lastError,
  });

  const stop = async (): Promise<NgrokStatus> => {
    if (!proc) return status();
    const p = proc;
    proc = null;
    await new Promise<void>((resolve) => {
      p.once("close", () => resolve());
      try {
        p.kill();
      } catch {
        resolve();
      }
    });
    publicUrl = null;
    callbackUrl = null;
    localPort = null;
    return status();
  };

  const start = async (opts: { ngrokPath?: string; localPort: number; callbackPath?: string }): Promise<NgrokStatus> => {
    if (proc) return status();
    lastError = null;
    publicUrl = null;
    callbackUrl = null;
    localPort = opts.localPort;
    const ngrokPath = String(opts.ngrokPath || "ngrok").trim() || "ngrok";
    const callbackPath = String(opts.callbackPath || "/suno/callback").trim() || "/suno/callback";
    const webPort = 4040;

    const fetchPublicUrl = async () => {
      try {
        const res = await fetch(`http://127.0.0.1:${webPort}/api/tunnels`);
        if (!res.ok) return null;
        const json = (await res.json()) as { tunnels?: Array<{ public_url?: string }> };
        const urls = (json.tunnels || [])
          .map((t) => String(t.public_url || "").trim())
          .filter(Boolean);
        const https = urls.find((u) => u.startsWith("https://"));
        return https || urls[0] || null;
      } catch {
        return null;
      }
    };

    proc = spawn(
      ngrokPath,
      ["http", String(opts.localPort), "--log=stdout", "--log-format=json", "--web-addr", `127.0.0.1:${webPort}`],
      { windowsHide: true },
    );

    proc.on("error", (e) => {
      lastError = e instanceof Error ? e.message : "failed to start ngrok";
    });

    let buf = "";
    const onChunk = (chunk: Buffer) => {
      buf += chunk.toString("utf-8");
      let idx = buf.indexOf("\n");
      while (idx >= 0) {
        const line = buf.slice(0, idx).trim();
        buf = buf.slice(idx + 1);
        idx = buf.indexOf("\n");
        if (!line) continue;
        const obj = parseJsonLine(line);
        if (!obj) continue;
        const msg = typeof obj.msg === "string" ? obj.msg : "";
        const url = typeof obj.url === "string" ? obj.url : "";
        const err = typeof obj.err === "string" ? obj.err : "";
        if (err) lastError = err;
        if (!publicUrl && url && /started tunnel/i.test(msg)) {
          publicUrl = url;
          callbackUrl = `${url}${callbackPath.startsWith("/") ? callbackPath : `/${callbackPath}`}`;
        }
      }
    };

    proc.stdout.on("data", onChunk);
    proc.stderr.on("data", onChunk);

    const started = Date.now();
    while (Date.now() - started < 12_000) {
      if (lastError) break;
      if (publicUrl) break;
      const fromApi = await fetchPublicUrl();
      if (fromApi) {
        publicUrl = fromApi;
        callbackUrl = `${fromApi}${callbackPath.startsWith("/") ? callbackPath : `/${callbackPath}`}`;
        break;
      }
      await new Promise((r) => setTimeout(r, 200));
    }

    return status();
  };

  return { status, start, stop };
}
