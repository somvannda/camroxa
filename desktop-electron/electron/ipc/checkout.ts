/**
 * In-app checkout modal.
 *
 * ChmabaPay is still the payment provider; the only change is that its hosted
 * page opens in a modal window owned by the app instead of the system browser.
 * The renderer polls `/topups/payments/{id}` and closes this window when the
 * payment is fulfilled.
 */
import { BrowserWindow, ipcMain, shell } from "electron";
import { z } from "zod";
import { logger } from "../services/logger";
import { ok } from "../shared/types";
import { toError } from "./errors";

const openSchema = z.object({ url: z.string().url().max(2048) }).strict();

let checkoutWindow: BrowserWindow | null = null;

function allowedCheckoutUrl(raw: string): boolean {
  try {
    const url = new URL(raw);
    if (url.protocol !== "https:") return false;
    const host = url.hostname.toLowerCase();
    return !["localhost", "127.0.0.1", "0.0.0.0"].includes(host);
  } catch {
    return false;
  }
}

export interface CheckoutIpcOptions {
  getWindow: () => BrowserWindow | null;
}

export function registerCheckoutIpc(options: CheckoutIpcOptions): void {
  ipcMain.handle("checkout:open", (event, payload: unknown) => {
    try {
      const input = openSchema.parse(payload);
      if (!allowedCheckoutUrl(input.url)) {
        return toError(new Error("The checkout link is not a secure web address."));
      }
      const parent = options.getWindow();
      if (!parent) return toError(new Error("The Camxora window is not available."));

      if (checkoutWindow && !checkoutWindow.isDestroyed()) {
        checkoutWindow.close();
        checkoutWindow = null;
      }

      const window = new BrowserWindow({
        parent,
        modal: true,
        width: 520,
        height: 820,
        minWidth: 420,
        minHeight: 640,
        title: "Camxora checkout",
        autoHideMenuBar: true,
        show: false,
        backgroundColor: "#0a0e27",
        webPreferences: {
          nodeIntegration: false,
          contextIsolation: true,
          sandbox: true,
          spellcheck: false,
        },
      });
      checkoutWindow = window;

      window.webContents.setWindowOpenHandler(({ url }) => {
        if (/^https?:\/\//i.test(url)) void shell.openExternal(url);
        return { action: "deny" };
      });
      window.webContents.on("will-navigate", (navigateEvent, url) => {
        if (!/^https?:\/\//i.test(url)) navigateEvent.preventDefault();
      });
      window.once("ready-to-show", () => window.show());
      window.on("closed", () => {
        if (checkoutWindow === window) checkoutWindow = null;
      });
      void window.loadURL(input.url).catch((error: unknown) => {
        logger.warn("checkout load failed", { error: String(error) });
      });
      // Keep the sender alive; the renderer polls payment status itself.
      void event;
      return ok({ opened: true });
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("checkout:close", () => {
    if (checkoutWindow && !checkoutWindow.isDestroyed()) {
      checkoutWindow.close();
    }
    checkoutWindow = null;
    return ok({ closed: true });
  });
}
