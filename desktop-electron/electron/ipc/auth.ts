import { ipcMain, shell } from "electron";
import { z } from "zod";
import {
  ApiClientError,
  bootstrapSession,
  completeGoogleLogin,
  login,
  requestGoogleAuthUrl,
} from "../services/api-client";
import { DEFAULT_LOOPBACK_PORT, GoogleLoopbackServer, GoogleOAuthError } from "../services/google-oauth";
import { logger } from "../services/logger";
import { sessionStore } from "../services/session";
import { fail, ok } from "../shared/types";
import { toError } from "./errors";

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
  remember: z.boolean().optional().default(true),
});

const googleSchema = z
  .object({
    remember: z.boolean().optional().default(true),
  })
  .optional();

const openExternalSchema = z.object({
  url: z
    .string()
    .url()
    .refine((value) => /^https:\/\//i.test(value), "Only https links can be opened."),
});

interface ActiveGoogleFlow {
  cancelled: boolean;
  loopback: GoogleLoopbackServer;
}

let googleFlow: ActiveGoogleFlow | null = null;

function toAuthError(error: unknown) {
  if (error instanceof GoogleOAuthError) {
    return fail(error.code, error.message, undefined, error.code !== "OAUTH_CANCELLED");
  }
  return toError(error);
}

/**
 * System-browser Google sign-in:
 * loopback listener -> GET /auth/google/url -> openExternal -> one callback ->
 * POST /auth/google/callback -> bootstrap.
 */
async function runGoogleFlow(remember: boolean) {
  if (googleFlow) {
    throw new GoogleOAuthError(
      "OAUTH_IN_PROGRESS",
      "Google sign-in is already in progress.",
    );
  }

  const loopback = new GoogleLoopbackServer();
  const flow: ActiveGoogleFlow = { cancelled: false, loopback };
  googleFlow = flow;

  try {
    await loopback.start();
    if (flow.cancelled) {
      throw new GoogleOAuthError("OAUTH_CANCELLED", "Google sign-in was cancelled.");
    }

    const { url, state } = await requestGoogleAuthUrl(loopback.port);
    if (flow.cancelled) {
      throw new GoogleOAuthError("OAUTH_CANCELLED", "Google sign-in was cancelled.");
    }

    await shell.openExternal(url);
    logger.info("google sign-in opened in browser", { port: loopback.port });

    const callback = await loopback.wait();
    if (flow.cancelled) {
      throw new GoogleOAuthError("OAUTH_CANCELLED", "Google sign-in was cancelled.");
    }
    if (callback.state !== state) {
      throw new GoogleOAuthError(
        "OAUTH_ERROR",
        "Google sign-in could not be verified. Please try again.",
      );
    }

    return await completeGoogleLogin(callback.code, callback.state, remember);
  } finally {
    loopback.close();
    if (googleFlow === flow) googleFlow = null;
  }
}

export function registerAuthIpc(): void {  ipcMain.handle("auth:login", async (_event, payload: unknown) => {
    try {
      const input = loginSchema.parse(payload);
      return ok(await login(input.email, input.password, input.remember));
    } catch (error) {
      return toAuthError(error);
    }
  });

  ipcMain.handle("auth:google-available", async () => {
    try {
      await requestGoogleAuthUrl(DEFAULT_LOOPBACK_PORT);
      return ok({ available: true, message: null });
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 503) {
        return ok({
          available: false,
          message: "Google sign-in is not configured on this server. Use email and password.",
        });
      }
      // Transient/network/unknown states keep the button usable: clicking gives
      // the specific failure instead of disabling sign-in on a bad probe.
      return ok({ available: true, message: null });
    }
  });

  ipcMain.handle("auth:google", async (_event, payload: unknown) => {
    try {
      const input = googleSchema.parse(payload) ?? { remember: true };
      return ok(await runGoogleFlow(input.remember));
    } catch (error) {
      return toAuthError(error);
    }
  });

  ipcMain.handle("auth:google-cancel", () => {
    if (googleFlow) {
      googleFlow.cancelled = true;
      googleFlow.loopback.cancel();
      logger.info("google sign-in cancelled");
    }
    return ok(true);
  });

  ipcMain.handle("auth:restore", async () => {
    try {
      return ok(await bootstrapSession());
    } catch (error) {
      return toAuthError(error);
    }
  });

  ipcMain.handle("auth:bootstrap", async () => {
    try {
      return ok(await bootstrapSession());
    } catch (error) {
      return toAuthError(error);
    }
  });

  ipcMain.handle("auth:logout", () => {
    sessionStore.clear();
    logger.info("user signed out");
    return ok(true);
  });

  ipcMain.handle("auth:saved-accounts", () => {
    const account = sessionStore.accountSummary();
    return ok(account ? [account] : []);
  });

  ipcMain.handle("app:open-external", async (_event, payload: unknown) => {
    const parsed = openExternalSchema.safeParse(payload);
    if (!parsed.success) {
      return fail("INVALID_URL", "Only secure links can be opened.");
    }
    try {
      await shell.openExternal(parsed.data.url);
      return ok(true);
    } catch (error) {
      logger.warn("could not open external link", { error: String(error) });
      return fail("OPEN_EXTERNAL_FAILED", "Could not open the link in your browser.", undefined, true);
    }
  });
}
