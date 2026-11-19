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

const exportSchema = z
  .object({
    width: z.number().finite().min(16).max(7680).optional(),
    height: z.number().finite().min(16).max(7680).optional(),
    fps: z.number().finite().min(1).max(120).optional(),
    format: z.enum(["mp4", "webm"]).optional(),
    codec: z.enum(["h264", "vp8", "vp9"]).optional(),
    bitrate: z.number().finite().min(0).max(200).optional(),
    crf: z.number().finite().min(0).max(51).optional(),
    start: z.number().finite().min(0).max(86_400).optional(),
    end: z.number().finite().min(0).max(86_400).optional(),
  })
  .strict()
  .nullish();

const renderNameSchema = z.object({ name: z.string().min(1).max(160) });

const exportChunkSchema = z.object({
  jobId: z.string().uuid(),
  position: z.number().int().min(0),
  data: z.instanceof(Uint8Array),
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

  /* export + managed renders ------------------------------------------ */

  ipcMain.handle("vizzy:export", async (event, payload: unknown) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      const settings = exportSchema.parse(payload);
      const outcome = await host.exportVideo(settings ?? null);
      if (outcome.status === "failed") {
        return fail("VIZZY_EXPORT_FAILED", outcome.message);
      }
      return ok(outcome);
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("vizzy:export:cancel", (event, payload: unknown) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      const { jobId } = z.object({ jobId: z.string().uuid() }).parse(payload);
      return ok({ cancelled: host.cancelExport(jobId) });
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("vizzy:renders:list", (event) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      return ok(host.listRenders());
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("vizzy:renders:delete", (event, payload: unknown) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      const { name } = renderNameSchema.parse(payload);
      return ok({ deleted: host.deleteRender(name) });
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("vizzy:renders:reveal", (event, payload: unknown) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      const { name } = renderNameSchema.parse(payload);
      return ok(host.revealRender(name));
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("vizzy:renders:url", (event, payload: unknown) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      const { name } = renderNameSchema.parse(payload);
      const url = host.renderUrl(name);
      if (!url) return fail("VIZZY_RENDER_NOT_FOUND", "That render is no longer available.");
      return ok({ url });
    } catch (error) {
      return toError(error);
    }
  });

  /* view-origin ------------------------------------------------------ */

  // The editor streams encoder chunks here, one at a time, at absolute offsets.
  ipcMain.handle("vizzy:export:chunk", async (event, payload: unknown) => {
    if (!viewOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      const chunk = exportChunkSchema.parse(payload);
      return ok(await host.writeExportChunk(chunk));
    } catch (error) {
      return toError(error);
    }
  });

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
