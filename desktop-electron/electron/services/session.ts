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
  private remembered = false;

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

  /**
   * Stores the token pair in memory and, when `remember` is true, on disk via
   * `safeStorage`. Omitting `remember` keeps the current persistence choice so
   * a token refresh cannot start (or stop) remembering a session on its own.
   */
  save(tokens: AuthTokens, account?: SavedAccount, remember?: boolean): void {
    this.tokens = tokens;
    if (account) this.account = account;
    if (remember !== undefined) this.remembered = remember;
    this.persist();
  }

  /** Updates the saved account summary after `/users/me` resolves. */
  updateAccount(account: SavedAccount): void {
    this.account = account;
    if (!this.tokens) return;
    this.persist();
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
      this.remembered = true;
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
    this.remembered = false;
    try {
      fs.rmSync(this.filePath(), { force: true });
    } catch {
      // ignore
    }
  }

  private persist(): void {
    const tokens = this.tokens;
    if (!tokens) return;
    if (!this.remembered) {
      // "Remember me" unchecked: the session lives in memory for this run only.
      try {
        fs.rmSync(this.filePath(), { force: true });
      } catch {
        // ignore
      }
      return;
    }

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
}

export const sessionStore = new SessionStore();
