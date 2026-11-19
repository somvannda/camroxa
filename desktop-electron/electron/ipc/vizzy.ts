/**
 * IPC surface for the hosted Vizzy editor.
 *
 * Two senders, two rules:
 *  - the shell renderer owns attach/detach/bounds/save/open/probe;
 *  - the hosted view owns the bridge lifecycle messages and its own save/open.
 *
 * Every handler checks the sender id, so a compromised renderer cannot drive the
 * other side's channels.
 */
import { ipcMain, type WebContents } from "electron";
import { z } from "zod";
import { VIZZY_BRIDGE_CHANNEL } from "../vizzy-host/bridge";
import type { VizzyHost } from "../vizzy-host/host";
import { fail, ok } from "../shared/types";
import { toError } from "./errors";

const boundsSchema = z.object({
  x: z.number().finite(),
  y: z.number().finite(),
  width: z.number().finite(),
  height: z.number().finite(),
});

const pathSchema = z.object({
  path: z.string().min(1),
});

const saveSchema = z.object({
  name: z.string().min(1).max(200),
  json: z.string().min(2),
});

export function registerVizzyIpc(host: VizzyHost): void {
  const shellOnly = (sender: WebContents): boolean => host.isShellSender(sender);
  const viewOnly = (sender: WebContents): boolean => host.isViewSender(sender);

  ipcMain.handle("vizzy:attach", (event, payload: unknown) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      const bounds = boundsSchema.parse(payload);
      return ok(host.attach(bounds));
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("vizzy:detach", (event) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    host.detach();
    return ok(true);
  });

  ipcMain.handle("vizzy:set-bounds", (event, payload: unknown) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      host.setBounds(boundsSchema.parse(payload));
      return ok(true);
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("vizzy:state", (event) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    return ok(host.getState());
  });

  ipcMain.handle("vizzy:probe", async (event) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      const probe = await host.probe();
      if (!probe) return fail("VIZZY_NOT_ATTACHED", "The Vizzy editor is not running.");
      return ok(probe);
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("vizzy:reload", (event) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    host.reload();
    return ok(true);
  });

  ipcMain.handle("vizzy:save", async (event) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      return ok(await host.saveCurrent());
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("vizzy:open", async (event) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      return ok(await host.openFromDialog());
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("vizzy:open-path", async (event, payload: unknown) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      const input = pathSchema.parse(payload);
      return ok(await host.openPath(input.path));
    } catch (error) {
      return toError(error);
    }
  });

  /* view-origin ------------------------------------------------------ */

  ipcMain.on(VIZZY_BRIDGE_CHANNEL, (event, message: unknown) => {
    if (!viewOnly(event.sender)) return;
    void host.handleViewMessage(message);
  });

  ipcMain.handle("vizzy:project:save", (event, payload: unknown) => {
    if (!viewOnly(event.sender)) throw new Error("Wrong sender for this channel.");
    const input = saveSchema.parse(payload);
    const result = host.saveProject(input.name, input.json);
    return { path: result.path, name: result.name };
  });

  ipcMain.handle("vizzy:project:open", async (event) => {
    if (!viewOnly(event.sender)) throw new Error("Wrong sender for this channel.");
    return host.openFromDialog();
  });
}
