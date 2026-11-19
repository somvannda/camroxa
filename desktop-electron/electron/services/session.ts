import fs from "node:fs";
import path from "node:path";
import { safeStorage } from "electron";
import { ensureAppDirs, getAppPaths } from "./paths";
import type { AuthTokens, SavedAccount } from "../shared/types";

interface StoredSession {
  tokens: AuthTokens;
  account?: SavedAccount;
}

class SessionStore {
  private tokens: AuthTokens | null = null;
  private account: SavedAccount | null = null;

  private filePath(): string {
    return path.join(getAppPaths().userData, "session.bin");
  }

  encryptionAvailable(): boolean {
    try {
      return safeStorage.isEncryptionAvailable();
    } catch {
      return false;
    }
  }

  save(tokens: AuthTokens, account?: SavedAccount, remember = true): void {
    this.tokens = tokens;
    if (account) this.account = account;
    if (!remember) return;

    try {
      ensureAppDirs();
      const payload: StoredSession = { tokens, account: this.account ?? undefined };
      const raw = JSON.stringify(payload);
      const encoded = this.encryptionAvailable()
        ? safeStorage.encryptString(raw).toString("base64")
        : Buffer.from(raw, "utf8").toString("base64");
      fs.writeFileSync(this.filePath(), encoded, "utf8");
    } catch {
      // Keep the in-memory session even if disk persistence fails.
    }
  }

  load(): AuthTokens | null {
    if (this.tokens) return this.tokens;
    try {
      if (!fs.existsSync(this.filePath())) return null;
      const encoded = fs.readFileSync(this.filePath(), "utf8").trim();
      if (!encoded) return null;
      const raw = this.encryptionAvailable()
        ? safeStorage.decryptString(Buffer.from(encoded, "base64"))
        : Buffer.from(encoded, "base64").toString("utf8");
      const parsed = JSON.parse(raw) as StoredSession;
      if (!parsed?.tokens?.accessToken || !parsed?.tokens?.refreshToken) return null;
      this.tokens = parsed.tokens;
      this.account = parsed.account ?? null;
      return this.tokens;
    } catch {
      return null;
    }
  }

  accountSummary(): SavedAccount | null {
    this.load();
    return this.account;
  }

  clear(): void {
    this.tokens = null;
    this.account = null;
    try {
      fs.rmSync(this.filePath(), { force: true });
    } catch {
      // ignore
    }
  }
}

export const sessionStore = new SessionStore();
