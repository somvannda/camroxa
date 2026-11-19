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
import fs from "node:fs";
import path from "node:path";
import { ipcMain, type WebContents } from "electron";
import { z } from "zod";
import { probe } from "../services/ffmpeg";
import { allowPickedFile, createMediaUrl } from "../services/media";
import { getAppPaths } from "../services/paths";
import {
  collectBindingOptions,
  detectBindings,
  type PipelineRunInputs,
  type ProjectSnapshot,
} from "../services/pipeline-templates";
import { buildPipelineRenderPlan } from "../services/pipeline-run";
import { readVideoTemplate, saveVideoTemplate } from "../services/video-templates";
import {
  bindingsFromSelection,
  firstBindingError,
  inferKind,
  kindAspectError,
  selectionFromDetected,
  validateBindingSelection,
  type BindingSelection,
} from "../shared/pipeline";
import { VIZZY_BRIDGE_CHANNEL } from "../vizzy-host/bridge";
import type { VizzyHost } from "../vizzy-host/host";
import { fail, ok } from "../shared/types";
import { toError } from "./errors";
import { notifyVideoTemplatesChanged, toVideoTemplateInfo } from "./video-templates";

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

const idSchema = z.object({ id: z.string().min(1).max(200) });

const visibilitySchema = z.object({ visible: z.boolean() });

const bindingSelectionSchema = z
  .object({
    background: z.string().max(200),
    logo: z.string().max(200),
    title: z.string().max(200),
    artist: z.string().max(200),
    album: z.string().max(200),
    palette: z.string().max(200),
  })
  .strict();

const saveTemplateSchema = z
  .object({
    name: z.string().trim().min(1).max(200),
    kind: z.enum(["long", "reel"]),
    bindings: bindingSelectionSchema,
  })
  .strict();

const renderTemplateSchema = z
  .object({
    templateId: z.string().min(1).max(200),
    audioPath: z.string().min(1).max(4096),
    title: z.string().max(300).optional(),
    artist: z.string().max(300).optional(),
    album: z.string().max(300).optional(),
    backgroundPath: z.string().min(1).max(4096).optional(),
    logoPath: z.string().min(1).max(4096).optional(),
    palette: z
      .array(z.string().regex(/^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/))
      .max(16)
      .optional(),
  })
  .strict();

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function numberOf(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function textOf(value: unknown): string {
  return typeof value === "string" ? value : "";
}

/** Absolute path → opaque, displayable `camxora-media://` URL for the editor. */
function mediaUrlFor(filePath: string, role: string): string {
  const resolved = path.resolve(filePath);
  let stat: fs.Stats;
  try {
    stat = fs.statSync(resolved);
  } catch {
    throw new Error(`The ${role} file does not exist: ${resolved}`);
  }
  if (!stat.isFile()) throw new Error(`The ${role} path is not a file.`);
  if (stat.size <= 0) throw new Error(`The ${role} file is empty.`);
  allowPickedFile(resolved);
  return createMediaUrl(resolved);
}

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

  /* video templates -------------------------------------------------- */

  ipcMain.handle("vizzy:set-visible", (event, payload: unknown) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      const { visible } = visibilitySchema.parse(payload);
      host.setVisible(visible);
      return ok(true);
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("vizzy:template-options", async (event) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    if (!host.hasView() || !host.getState().ready) {
      return fail("VIZZY_NOT_READY", "Open the Vizzy editor and wait for it to finish loading.");
    }
    try {
      const { snapshot } = await host.readSnapshot();
      const project = (snapshot.project ?? {}) as Record<string, unknown>;
      const width = numberOf(project.width, 1920);
      const height = numberOf(project.height, 1080);
      const fps = numberOf(project.fps, 30);
      const options = collectBindingOptions(snapshot as ProjectSnapshot);
      const detected = selectionFromDetected(
        detectBindings(snapshot as ProjectSnapshot),
        options,
      );
      return ok({
        name: textOf(project.name) || host.getState().projectName || "Untitled template",
        width,
        height,
        fps,
        kind: inferKind(width, height),
        detected,
        options,
      });
    } catch (error) {
      return fail("VIZZY_NOT_READY", messageOf(error));
    }
  });

  ipcMain.handle("vizzy:save-template", async (event, payload: unknown) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    let input: z.infer<typeof saveTemplateSchema>;
    try {
      input = saveTemplateSchema.parse(payload);
    } catch {
      return fail("INVALID_REQUEST", "The template request is not valid.");
    }
    if (!host.hasView() || !host.getState().ready) {
      return fail("VIZZY_NOT_READY", "Open the Vizzy editor and wait for it to finish loading.");
    }
    try {
      // Capture the exact preview and the thumbnail in one step, so the saved
      // project is the one the user was looking at.
      const source = await host.captureTemplateSource();
      const project = (source.snapshot.project ?? {}) as Record<string, unknown>;
      const width = numberOf(project.width, 1920);
      const height = numberOf(project.height, 1080);
      const options = collectBindingOptions(source.snapshot as ProjectSnapshot);
      const fieldErrors = validateBindingSelection(options, input.bindings);
      const kindError = kindAspectError(input.kind, width, height);
      const firstError = kindError ?? firstBindingError(fieldErrors);
      if (firstError) {
        return fail("TEMPLATE_INVALID", firstError, { fields: fieldErrors, kind: kindError });
      }
      const bindings = bindingsFromSelection(input.bindings as BindingSelection);
      const saved = saveVideoTemplate({
        root: getAppPaths().templates,
        name: input.name,
        snapshotJson: source.json,
        thumbnail: source.thumbnail,
        bindings,
        kind: input.kind,
      });
      notifyVideoTemplatesChanged({ id: saved.id, action: "saved" });
      return ok(toVideoTemplateInfo(saved));
    } catch (error) {
      return fail("TEMPLATE_SAVE_FAILED", messageOf(error));
    }
  });

  ipcMain.handle("vizzy:preview-template", async (event, payload: unknown) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    let id: string;
    try {
      id = idSchema.parse(payload).id;
    } catch {
      return fail("INVALID_REQUEST", "The template id is not valid.");
    }
    let detail: ReturnType<typeof readVideoTemplate>;
    try {
      detail = readVideoTemplate(getAppPaths().templates, id);
    } catch (error) {
      return fail("TEMPLATE_NOT_FOUND", messageOf(error));
    }
    if (!host.hasView()) {
      return fail("VIZZY_NOT_ATTACHED", "Open the Vizzy editor first.");
    }
    try {
      const opened = await host.openProjectJson({
        json: detail.projectJson,
        name: detail.name,
        path: null,
      });
      return ok(opened);
    } catch (error) {
      return fail("TEMPLATE_PREVIEW_FAILED", messageOf(error));
    }
  });

  ipcMain.handle("vizzy:open-library", async (event) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      return ok({ opened: await host.openCreationsBrowser() });
    } catch (error) {
      return fail("VIZZY_LIBRARY_FAILED", messageOf(error));
    }
  });

  ipcMain.handle("vizzy:render-template", async (event, payload: unknown) => {
    if (!shellOnly(event.sender)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    let request: z.infer<typeof renderTemplateSchema>;
    try {
      request = renderTemplateSchema.parse(payload);
    } catch {
      return fail("INVALID_REQUEST", "The render request is not valid.");
    }

    let detail: ReturnType<typeof readVideoTemplate>;
    try {
      detail = readVideoTemplate(getAppPaths().templates, request.templateId);
    } catch (error) {
      return fail("TEMPLATE_NOT_FOUND", messageOf(error));
    }

    const expectedKind = inferKind(detail.pipeline.output.width, detail.pipeline.output.height);
    if (detail.pipeline.kind !== expectedKind) {
      return fail(
        "TEMPLATE_KIND_MISMATCH",
        `This template declares ${detail.pipeline.kind} but its ${detail.pipeline.output.width}×${detail.pipeline.output.height} output is ${expectedKind}.`,
      );
    }

    const audioPath = path.resolve(request.audioPath);
    let audioStat: fs.Stats;
    try {
      audioStat = fs.statSync(audioPath);
    } catch {
      return fail("AUDIO_FILE_MISSING", `The audio file does not exist: ${audioPath}`);
    }
    if (!audioStat.isFile()) return fail("AUDIO_FILE_MISSING", "The audio path is not a file.");
    if (audioStat.size <= 0) return fail("AUDIO_FILE_EMPTY", "The audio file is empty.");

    if (!host.hasView() || !host.getState().ready) {
      return fail("VIZZY_NOT_READY", "Open the Vizzy editor and wait for it to finish loading.");
    }

    let inputs: PipelineRunInputs;
    try {
      inputs = {
        title: request.title,
        artist: request.artist,
        album: request.album,
        palette: request.palette,
      };
      if (request.backgroundPath) {
        inputs.backgroundUrl = mediaUrlFor(request.backgroundPath, "background");
      }
      if (request.logoPath) {
        inputs.logoUrl = mediaUrlFor(request.logoPath, "logo");
      }
    } catch (error) {
      return fail("TEMPLATE_ASSET_MISSING", messageOf(error));
    }

    let audioDurationSec = 0;
    try {
      audioDurationSec = (await probe(audioPath)).durationSec;
    } catch (error) {
      return fail("AUDIO_UNREADABLE", messageOf(error));
    }
    if (!Number.isFinite(audioDurationSec) || audioDurationSec <= 0) {
      return fail("AUDIO_UNREADABLE", "The run audio has no usable duration.");
    }

    let plan: ReturnType<typeof buildPipelineRenderPlan>;
    try {
      plan = buildPipelineRenderPlan(
        { id: detail.id, projectJson: detail.projectJson, pipeline: detail.pipeline },
        { audioDurationSec, inputs, expectedKind: detail.pipeline.kind },
      );
    } catch (error) {
      return fail("TEMPLATE_BINDING_MISSING", messageOf(error));
    }

    try {
      await host.openProjectJson({ json: plan.projectJson, name: detail.name, path: null });
      await host.loadAudioTrack(audioPath);
      const outcome = await host.exportVideo(
        {
          width: plan.settings.width,
          height: plan.settings.height,
          fps: plan.settings.fps,
          format: "mp4",
          codec: "h264",
          bitrate: plan.settings.bitrate,
          crf: plan.settings.crf,
          start: plan.settings.start,
          end: plan.settings.end,
        },
        { outputName: detail.id },
      );
      if (outcome.status === "failed") {
        return fail("VIZZY_RENDER_FAILED", outcome.message);
      }
      return ok(outcome);
    } catch (error) {
      return fail("VIZZY_RENDER_FAILED", messageOf(error));
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
