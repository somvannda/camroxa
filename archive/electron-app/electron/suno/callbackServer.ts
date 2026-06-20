import { createServer, type IncomingMessage } from "node:http";

export type SunoCallbackServer = {
  port: number;
  close: () => Promise<void>;
};

async function readJson(req: IncomingMessage) {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of req) {
    const buf = Buffer.isBuffer(chunk) ? chunk : Buffer.from(String(chunk));
    size += buf.length;
    if (size > 2_000_000) throw new Error("payload too large");
    chunks.push(buf);
  }
  const raw = Buffer.concat(chunks).toString("utf-8");
  if (!raw.trim()) return null;
  return JSON.parse(raw) as unknown;
}

export async function startSunoCallbackServer(opts: {
  path?: string;
  onCallback: (payload: unknown) => void | Promise<void>;
}) : Promise<SunoCallbackServer> {
  const cbPath = opts.path ?? "/suno/callback";

  const server = createServer(async (req, res) => {
    try {
      const url = new URL(req.url || "", `http://${req.headers.host || "localhost"}`);
      if (req.method !== "POST" || url.pathname !== cbPath) {
        res.statusCode = 404;
        res.end("not found");
        return;
      }
      const payload = await readJson(req);
      await opts.onCallback(payload);
      res.statusCode = 200;
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ ok: true }));
    } catch (e) {
      res.statusCode = 400;
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ ok: false, message: e instanceof Error ? e.message : "bad request" }));
    }
  });

  await new Promise<void>((resolve, reject) => {
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => resolve());
  });

  const addr = server.address();
  const port = typeof addr === "object" && addr ? addr.port : 0;

  return {
    port,
    close: async () => {
      await new Promise<void>((resolve) => server.close(() => resolve()));
    },
  };
}

