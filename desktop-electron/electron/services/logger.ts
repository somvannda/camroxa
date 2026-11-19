import fs from "node:fs";
import path from "node:path";
import { ensureAppDirs, getAppPaths } from "./paths";
import { redact } from "./redact";

type Level = "info" | "warn" | "error";

function logFilePath(): string {
  const day = new Date().toISOString().slice(0, 10);
  return path.join(getAppPaths().logs, `app-${day}.log`);
}

function write(level: Level, message: string, detail?: unknown): void {
  try {
    ensureAppDirs();
    const entry = {
      ts: new Date().toISOString(),
      level,
      message,
      ...(detail === undefined ? {} : { detail: redact(detail) }),
    };
    fs.appendFileSync(logFilePath(), `${JSON.stringify(entry)}\n`, "utf8");
  } catch {
    // Logging must never take the app down.
  }
}

export const logger = {
  info: (message: string, detail?: unknown) => write("info", message, detail),
  warn: (message: string, detail?: unknown) => write("warn", message, detail),
  error: (message: string, detail?: unknown) => write("error", message, detail),
  file: logFilePath,
};
