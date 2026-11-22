/**
 * Manual YouTube upload (Progress row action).
 *
 * This is the 1.7.1 "Upload to YouTube" flow ported to the Electron main
 * process: a short-lived access token from the platform API, a publish job for
 * billing/bookkeeping, a direct resumable upload from disk, then the report and
 * completion calls. It is only ever started by an explicit user action —
 * Auto-Upload stays disabled exactly as in 1.7.1.
 *
 * Security notes:
 * - the access token lives in a local variable and is never returned, logged or
 *   attached to an error;
 * - the file must sit inside this run folder or the managed downloads/renders
 *   roots (see `youtube-contain.ts`);
 * - only one upload runs at a time and cancelling aborts the request without
 *   touching the local file.
 */
import { randomUUID } from "node:crypto";
import path from "node:path";
import { ApiClientError, apiRequest } from "./api-client";
import { logger } from "./logger";
import { getAppPaths } from "./paths";
import { redactString } from "./redact";
import { getStore } from "./store";
import { readVideoTemplate } from "./video-templates";
import {
  buildMetadata,
  buildPublishJobPayload,
  videoUrl,
  visibilityLabel,
  youtubeInsertBody,
  type PublicationMetadata,
} from "./youtube-metadata";
import {
  discoverMergedFile,
  resolveContainedVideo,
  thumbnailBeside,
  UploadFileError,
  type ContainedFile,
} from "./youtube-contain";
import {
  addToPlaylist,
  resolveChunkBytes,
  resolveYoutubeEndpoints,
  startResumableSession,
  uploadResumable,
  YoutubeUploadError,
} from "./youtube-resumable";
import type { PipelineBatchRecord } from "./database";
import type {
  ApiRequest,
  YoutubeAvailability,
  YoutubeChannelSummary,
  YoutubePlaylistOption,
  YoutubeUploadPlan,
  YoutubeUploadRowQuery,
  YoutubeUploadRowState,
  YoutubeUploadSnapshot,
  YoutubeUploadStartRequest,
  YoutubeUploadState,
} from "../shared/types";

interface ProfileLite {
  id: string;
  name: string;
  youtubeConfig: Record<string, unknown>;
  videoTemplateId: string;
  reelTemplateId: string;
}

interface UploadContext {
  profiles: ProfileLite[];
  connections: Map<string, { connected: boolean; channelTitle: string | null }>;
  quota: { remaining: number; limit: number } | null;
  error: string | null;
}

interface ActiveUpload {
  state: YoutubeUploadState;
  controller: AbortController;
}

export interface YoutubeUploadDeps {
  api?: (request: ApiRequest) => Promise<{ data: unknown }>;
  emit?: (upload: YoutubeUploadState) => void;
  fetchImpl?: typeof fetch;
  env?: NodeJS.ProcessEnv;
  managedRoots?: () => string[];
  batches?: () => PipelineBatchRecord[];
  /** Resolve a portable server run key against the device Suno folder. */
  resolvePath?: (value: string) => string;
  videoTemplateExists?: (id: string) => boolean;
  now?: () => number;
  historyLimit?: number;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function asNumber(value: unknown): number | null {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? number : null;
}

function profileFrom(value: unknown): ProfileLite | null {
  const record = asRecord(value);
  const id = asString(record.id);
  if (!id) return null;
  return {
    id,
    name: asString(record.name) ?? "",
    youtubeConfig: asRecord(record.youtube_config),
    videoTemplateId: asString(record.video_template_id) ?? "",
    reelTemplateId: asString(record.reel_template_id) ?? "",
  };
}

function defaultManagedRoots(): string[] {
  const paths = getAppPaths();
  return [paths.downloads, paths.renders];
}

export function errorText(error: unknown): string {
  const raw =
    error instanceof YoutubeUploadError || error instanceof UploadFileError
      ? error.message
      : error instanceof ApiClientError
        ? error.message || `Request failed (${error.status}).`
        : error instanceof Error
          ? error.message
          : "The upload failed.";
  // Provider/API text can echo an address; never surface it in the UI.
  return redactString(String(raw));
}

function errorStatus(error: unknown): number | null {
  return error instanceof ApiClientError ? error.status : null;
}

function isRetryableApiError(error: unknown): boolean {
  return error instanceof ApiClientError ? error.retryable : false;
}

export class YoutubeUploadService {
  private readonly api: NonNullable<YoutubeUploadDeps["api"]>;
  private readonly emit: NonNullable<YoutubeUploadDeps["emit"]>;
  private readonly env: NodeJS.ProcessEnv;
  private readonly now: () => number;
  private readonly historyLimit: number;

  private active: ActiveUpload | null = null;
  private history: YoutubeUploadState[] = [];
  private contextCache: { at: number; value: Promise<UploadContext> } | null = null;

  constructor(private readonly deps: YoutubeUploadDeps = {}) {
    this.api = deps.api ?? apiRequest;
    this.emit = deps.emit ?? (() => undefined);
    this.env = deps.env ?? process.env;
    this.now = deps.now ?? (() => Date.now());
    this.historyLimit = Math.max(4, deps.historyLimit ?? 20);
  }

  // ------------------------------------------------------------------
  // Read-only surface
  // ------------------------------------------------------------------

  snapshot(): YoutubeUploadSnapshot {
    return {
      active: this.active?.state ?? null,
      history: this.history.slice(0, this.historyLimit),
    };
  }

  invalidate(): void {
    this.contextCache = null;
  }

  /** One lookup feeds the whole page: profiles, connections, quota, playlists. */
  async availability(rows: YoutubeUploadRowQuery[]): Promise<YoutubeAvailability> {
    const context = await this.loadContext();
    const states: YoutubeUploadRowState[] = [];
    for (const row of rows) states.push(this.rowState(row, context));

    const profileIds = [...new Set(rows.map((row) => row.profileId).filter(Boolean))].slice(0, 20);
    const channels: YoutubeChannelSummary[] = [];
    for (const profileId of profileIds) {
      const profile = context.profiles.find((item) => item.id === profileId) ?? null;
      const connection = context.connections.get(profileId);
      const playlists = await this.playlistsFor(profileId);
      const playlistId =
        typeof profile?.youtubeConfig.playlist === "string"
          ? String(profile.youtubeConfig.playlist).trim()
          : "";
      channels.push({
        profileId,
        profileName: profile?.name ?? "",
        connected: Boolean(connection?.connected),
        channelTitle: connection?.channelTitle ?? null,
        playlistId,
        playlistTitle: playlists.find((item) => item.id === playlistId)?.title ?? null,
        playlists,
      });
    }

    return {
      channel: channels[0] ?? null,
      channels,
      quotaRemaining: context.quota?.remaining ?? null,
      quotaLimit: context.quota?.limit ?? null,
      rows: states,
      error: context.error,
    };
  }

  /** Metadata for the confirmation dialog; nothing is uploaded here. */
  async plan(row: YoutubeUploadRowQuery): Promise<YoutubeUploadPlan> {
    const context = await this.loadContext();
    const state = this.rowState(row, context);
    if (state.block !== "none") {
      throw new UploadFileError(
        "UPLOAD_FILE_MISSING",
        state.reason ?? "This row cannot be uploaded right now.",
      );
    }
    const resolved = this.resolveRow(row, context);
    if (!resolved.profile || !resolved.file) {
      throw new UploadFileError("UPLOAD_FILE_MISSING", "This row cannot be uploaded right now.");
    }
    const metadata = this.metadataFor(resolved.profile, resolved.file);
    const connection = context.connections.get(resolved.profile.id);
    const playlists = await this.playlistsFor(resolved.profile.id);
    return {
      key: row.key,
      profileId: resolved.profile.id,
      channelTitle: connection?.channelTitle ?? resolved.profile.name,
      title: metadata.title,
      description: metadata.description,
      visibility: visibilityLabel(metadata),
      publishAt: metadata.publishAt,
      playlistId: metadata.playlistId,
      playlistTitle: playlists.find((item) => item.id === metadata.playlistId)?.title ?? null,
      mergedName: resolved.file.name,
      mergedBytes: resolved.file.bytes,
      tags: metadata.tags,
      category: metadata.category,
      madeForKids: metadata.madeForKids,
      containsSyntheticMedia: metadata.containsSyntheticMedia,
    };
  }

  // ------------------------------------------------------------------
  // Upload lifecycle
  // ------------------------------------------------------------------

  async start(request: YoutubeUploadStartRequest): Promise<YoutubeUploadState> {
    if (this.active) {
      throw new Error("A YouTube upload is already running. Wait for it or cancel it first.");
    }
    const context = await this.loadContext();
    const row: YoutubeUploadRowQuery = {
      key: request.key,
      batchId: request.batchId,
      profileId: request.profileId,
      role: request.role,
      runDir: request.runDir,
    };
    const resolved = this.resolveRow(row, context);
    if (!resolved.profile) {
      throw new Error("The channel profile for this upload was not found.");
    }
    if (!resolved.file) {
      throw new Error("No merged video was found for this run. Merge it first, then upload.");
    }
    const metadata = this.metadataFor(resolved.profile, resolved.file);
    const playlistId = await this.playlistForRequest(
      request.playlist,
      metadata,
      resolved.profile.id,
    );

    const state: YoutubeUploadState = {
      uploadId: randomUUID(),
      key: request.key,
      batchId: request.batchId,
      profileId: resolved.profile.id,
      phase: "queued",
      sentBytes: 0,
      totalBytes: resolved.file.bytes,
      percent: 0,
      message: "Preparing the upload…",
      title: metadata.title,
      videoId: null,
      videoUrl: null,
      jobUid: null,
      error: null,
      startedAt: this.now(),
      finishedAt: null,
    };
    const active: ActiveUpload = { state, controller: new AbortController() };
    this.active = active;
    this.push(state);

    void this.run(active, request, resolved.profile, resolved.file, metadata, playlistId);
    return { ...state };
  }

  cancel(uploadId?: string): boolean {
    if (!this.active) return false;
    if (uploadId && this.active.state.uploadId !== uploadId) return false;
    this.active.controller.abort();
    this.patch(this.active, { message: "Cancelling the upload…" });
    return true;
  }

  // ------------------------------------------------------------------
  // Internals
  // ------------------------------------------------------------------

  private async loadContext(): Promise<UploadContext> {
    const cached = this.contextCache;
    if (cached && this.now() - cached.at < 5000) return cached.value;
    const value = this.fetchContext();
    this.contextCache = { at: this.now(), value };
    try {
      return await value;
    } catch (error) {
      this.contextCache = null;
      throw error;
    }
  }

  private async fetchContext(): Promise<UploadContext> {
    let profiles: ProfileLite[] = [];
    let error: string | null = null;
    try {
      const response = await this.api({ method: "GET", path: "/profiles" });
      profiles = Array.isArray(response.data)
        ? response.data.map(profileFrom).filter((item): item is ProfileLite => Boolean(item))
        : [];
    } catch (cause) {
      error = errorText(cause);
      logger.warn("youtube upload: profiles unavailable", { error });
    }

    const connections = new Map<string, { connected: boolean; channelTitle: string | null }>();
    try {
      const response = await this.api({ method: "GET", path: "/youtube/connections" });
      const items = Array.isArray(asRecord(response.data).connections)
        ? (asRecord(response.data).connections as unknown[])
        : [];
      for (const item of items) {
        const record = asRecord(item);
        const profileId = asString(record.profile_id);
        if (!profileId) continue;
        const status = String(record.status ?? "").trim().toLowerCase();
        const channelId = asString(record.channel_id);
        const connected =
          status === "connected" ||
          (Boolean(channelId) &&
            !["not_connected", "disconnected", "pending_browser", "error", "revoked"].includes(status));
        connections.set(profileId, {
          connected,
          channelTitle: asString(record.channel_title),
        });
      }
    } catch (cause) {
      if (!error) error = errorText(cause);
      logger.warn("youtube upload: connections unavailable", { error: errorText(cause) });
    }

    let quota: { remaining: number; limit: number } | null = null;
    try {
      const response = await this.api({ method: "GET", path: "/youtube/quota" });
      const record = asRecord(response.data);
      const remaining = asNumber(record.remaining);
      const limit = asNumber(record.limit);
      if (remaining !== null && limit !== null) quota = { remaining, limit };
    } catch {
      // An older backend may not expose quota: the upload still proceeds and the
      // provider reports a quota refusal at upload time.
    }

    return { profiles, connections, quota, error };
  }

  private rowState(row: YoutubeUploadRowQuery, context: UploadContext): YoutubeUploadRowState {
    const resolved = this.resolveRow(row, context);
    const base = {
      key: row.key,
      profileId: row.profileId,
      mergedPath: resolved.file?.path ?? null,
      mergedName: resolved.file?.name ?? null,
      mergedBytes: resolved.file?.bytes ?? null,
    };

    if (this.active && this.active.state.key === row.key) {
      return { ...base, block: "uploading", reason: "This video is uploading to YouTube now." };
    }
    if (row.youtubeUrl) {
      return { ...base, block: "already-uploaded", reason: "This video is already on YouTube." };
    }
    if (!resolved.file) {
      return {
        ...base,
        block: "no-file",
        reason: "No merged video for this run yet. Merge it in the video pipeline, then upload.",
      };
    }
    if (!resolved.profile) {
      return {
        ...base,
        block: "no-channel",
        reason: "This row's channel profile was not found on the account.",
      };
    }
    const channel = context.connections.get(resolved.profile.id);
    if (!channel?.connected) {
      return {
        ...base,
        block: "no-channel",
        reason: `YouTube is not connected for ${resolved.profile.name}. Connect it in Settings → Profiles.`,
      };
    }
    if (context.quota && context.quota.remaining <= 0) {
      return {
        ...base,
        block: "quota",
        reason: `Daily YouTube quota reached (${context.quota.limit} uploads). It resets on Google's schedule, or connect your own Google app in Settings.`,
      };
    }
    if (this.isLegacyTemplateBlocked(resolved.profile)) {
      return {
        ...base,
        block: "legacy-template",
        reason:
          "This channel still points at a legacy Camxora template. 2.0.0 does not migrate it — re-author the video in Vizzy, select it in Settings → Profiles, then upload.",
      };
    }
    return { ...base, block: "none", reason: null };
  }

  private resolveRow(
    row: YoutubeUploadRowQuery,
    context: UploadContext,
  ): { profile: ProfileLite | null; file: ContainedFile | null } {
    const profile = context.profiles.find((item) => item.id === row.profileId) ?? null;
    const managedRoots = (this.deps.managedRoots ?? defaultManagedRoots)();
    const batches = this.deps.batches ? this.deps.batches() : this.storeBatches();
    const batch = batches.find((item) => item.batchId === row.batchId) ?? null;

    const candidates: Array<{ filePath: string; runDir: string | null }> = [];
    if (batch?.mergedOutput) {
      candidates.push({ filePath: batch.mergedOutput, runDir: batch.outputDir });
    }
    const runDirText = (this.deps.resolvePath ?? ((value: string) => value))(
      String(row.runDir ?? "").trim() || batch?.outputDir || "",
    );
    // A drive/filesystem root is not a run folder: refusing it keeps the
    // containment root meaningful instead of accepting "everything under C:\".
    const runDir =
      runDirText && path.parse(path.resolve(runDirText)).root !== path.resolve(runDirText)
        ? runDirText
        : "";
    if (runDir) {
      const discovered = discoverMergedFile(runDir);
      if (discovered) candidates.push({ filePath: discovered, runDir });
    }

    for (const candidate of candidates) {
      try {
        return {
          profile,
          file: resolveContainedVideo({
            filePath: candidate.filePath,
            runDir: candidate.runDir,
            managedRoots,
          }),
        };
      } catch (error) {
        logger.warn("youtube upload: candidate refused", {
          code: error instanceof UploadFileError ? error.code : "unknown",
        });
      }
    }
    return { profile, file: null };
  }

  private storeBatches(): PipelineBatchRecord[] {
    try {
      return getStore().listBatches();
    } catch {
      return [];
    }
  }

  private isLegacyTemplateBlocked(profile: ProfileLite): boolean {
    const templateId = profile.videoTemplateId || profile.reelTemplateId;
    if (!templateId) return false;
    const exists = this.deps.videoTemplateExists
      ? this.deps.videoTemplateExists
      : (id: string): boolean => {
          try {
            readVideoTemplate(getAppPaths().templates, id);
            return true;
          } catch {
            return false;
          }
        };
    return !exists(templateId);
  }

  private metadataFor(profile: ProfileLite, file: ContainedFile): PublicationMetadata {
    return buildMetadata({
      profile: { id: profile.id, name: profile.name, youtubeConfig: profile.youtubeConfig },
      videoPath: file.path,
      thumbnailPath: thumbnailBeside(file.path),
      now: new Date(this.now()),
    });
  }

  private async playlistForRequest(
    requested: string | undefined,
    metadata: PublicationMetadata,
    profileId: string,
  ): Promise<string> {
    const value = String(requested ?? "profile").trim();
    if (value === "profile") return metadata.playlistId;
    if (value === "none" || value === "") return "";
    const playlists = await this.playlistsFor(profileId);
    return playlists.some((item) => item.id === value) ? value : "";
  }

  private async playlistsFor(profileId: string): Promise<YoutubePlaylistOption[]> {
    try {
      const response = await this.api({
        method: "GET",
        path: `/youtube/profiles/${encodeURIComponent(profileId)}/playlists`,
      });
      const items = Array.isArray(asRecord(response.data).playlists)
        ? (asRecord(response.data).playlists as unknown[])
        : [];
      return items
        .map((item) => {
          const record = asRecord(item);
          const id = asString(record.id);
          return id ? { id, title: asString(record.title) ?? id } : null;
        })
        .filter((item): item is YoutubePlaylistOption => Boolean(item));
    } catch {
      return [];
    }
  }

  private async accessToken(profileId: string): Promise<string> {
    try {
      const response = await this.api({
        method: "POST",
        path: `/youtube/profiles/${encodeURIComponent(profileId)}/access-token`,
        timeoutMs: 30_000,
      });
      const accessToken = asString(asRecord(response.data).access_token);
      if (!accessToken) {
        throw new Error(
          "YouTube did not return an access token. Reconnect the channel in Settings → Profiles.",
        );
      }
      return accessToken;
    } catch (error) {
      if (errorStatus(error) === 401 || errorStatus(error) === 403) {
        throw new Error(
          "YouTube is not connected for this channel. Connect it in Settings → Profiles, then upload again.",
        );
      }
      throw new Error(`Could not get an upload token: ${errorText(error)}`);
    }
  }

  private async run(
    active: ActiveUpload,
    request: YoutubeUploadStartRequest,
    profile: ProfileLite,
    file: ContainedFile,
    metadata: PublicationMetadata,
    playlistId: string,
  ): Promise<void> {
    let jobUid = "";
    let videoId = "";
    try {
      this.patch(active, { phase: "preparing", message: "Checking the connected channel…" });
      const accessToken = await this.accessToken(profile.id);

      const retryUid = String(request.retryJobUid ?? "").trim();
      if (retryUid) {
        try {
          const retried = await this.api({
            method: "POST",
            path: `/publish/jobs/${encodeURIComponent(retryUid)}/retry`,
          });
          jobUid = asString(asRecord(retried.data).job_uid) ?? retryUid;
          this.patch(active, { jobUid });
        } catch (error) {
          if (isRetryableApiError(error)) throw error;
          jobUid = "";
        }
      }

      if (!jobUid) {
        this.patch(active, { message: "Creating the publish job…" });
        const payload = buildPublishJobPayload({
          profileId: profile.id,
          batchId: request.batchId,
          role: request.role,
          metadata,
          filePath: file.path,
          fileSizeBytes: file.bytes,
        });
        const created = await this.api({
          method: "POST",
          path: "/publish/jobs",
          body: payload,
          timeoutMs: 45_000,
        });
        const record = asRecord(created.data);
        jobUid = asString(record.job_uid) ?? "";
        if (!jobUid) throw new Error("The publisher did not return a job id.");
        this.patch(active, { jobUid });
        if (record.existing === true && String(record.status ?? "").toLowerCase() === "success") {
          const current = await this.api({
            method: "GET",
            path: `/publish/jobs/${encodeURIComponent(jobUid)}`,
          }).catch(() => null);
          const currentRecord = asRecord(current?.data);
          this.finish(active, {
            phase: "done",
            videoId: asString(currentRecord.youtube_video_id),
            videoUrl: asString(currentRecord.youtube_url),
            message: "This video is already on YouTube — nothing was uploaded again.",
            percent: 100,
          });
          return;
        }
      }

      this.patch(active, {
        phase: "uploading",
        message: "Uploading to YouTube…",
        totalBytes: file.bytes,
      });

      const endpoints = resolveYoutubeEndpoints(this.env);
      const sessionUrl = await startResumableSession({
        accessToken,
        body: youtubeInsertBody(metadata),
        sizeBytes: file.bytes,
        endpoint: endpoints.upload,
        fetchImpl: this.deps.fetchImpl,
        signal: active.controller.signal,
      });

      const result = await uploadResumable({
        sessionUrl,
        filePath: file.path,
        chunkBytes: resolveChunkBytes(this.env),
        fetchImpl: this.deps.fetchImpl,
        signal: active.controller.signal,
        isCancelled: () => active.controller.signal.aborted,
        onProgress: (progress) => this.progress(active, progress.sentBytes, progress.totalBytes),
      });
      videoId = result.videoId;
      const url = videoUrl(videoId);
      this.patch(active, { videoId, videoUrl: url, sentBytes: file.bytes, percent: 100 });

      let warning: string | null = null;
      if (playlistId) {
        this.patch(active, { message: "Adding the video to the playlist…" });
        try {
          await addToPlaylist({
            accessToken,
            playlistId,
            videoId,
            endpoint: endpoints.playlist,
            fetchImpl: this.deps.fetchImpl,
            signal: active.controller.signal,
          });
        } catch (error) {
          warning = errorText(error);
          logger.warn("youtube upload: playlist failed", { jobUid });
        }
      }

      this.patch(active, { phase: "recording", message: "Recording the result…" });
      await this.report({
        batchId: request.batchId,
        profileId: profile.id,
        role: request.role,
        videoId,
        videoUrl: url,
        title: metadata.title,
        status: "success",
      });
      await this.api({
        method: "POST",
        path: `/publish/jobs/${encodeURIComponent(jobUid)}/complete`,
        body: { checksum: null },
      });

      this.finish(active, {
        phase: "done",
        videoId,
        videoUrl: url,
        message: warning ? `Published to YouTube. ${warning}` : "Published to YouTube.",
        percent: 100,
      });
      logger.info("youtube upload complete", { jobUid, videoId, bytes: file.bytes });
    } catch (error) {
      const cancelled =
        active.controller.signal.aborted ||
        (error instanceof YoutubeUploadError && error.code === "YOUTUBE_CANCELLED");
      if (cancelled) {
        if (jobUid && !videoId) {
          // Release the reserved job so a later retry is not blocked by a
          // half-open publish job. Best-effort: the local file is untouched.
          void this.cancelJob(jobUid);
        }
        this.finish(active, {
          phase: "cancelled",
          message: "Upload cancelled. The local video was kept.",
        });
        logger.info("youtube upload cancelled", { jobUid });
        return;
      }

      const message = errorText(error);
      if (videoId) {
        // The video is live; only the bookkeeping write failed. Keep the link
        // and say so instead of reporting a false upload failure.
        this.finish(active, {
          phase: "done",
          videoId,
          videoUrl: active.state.videoUrl,
          message: `Published to YouTube, but recording the result failed. ${message}`,
          percent: 100,
        });
        logger.warn("youtube upload: bookkeeping failed after publish", {
          jobUid,
          videoId,
          error: message,
        });
        return;
      }
      // Failed before anything was published: record it so Progress stops
      // showing "Not started" for this row.
      void this.report({
        batchId: request.batchId,
        profileId: profile.id,
        role: request.role,
        videoId: "",
        videoUrl: null,
        title: metadata.title,
        status: "failed",
        errorMessage: message.slice(0, 500),
      });
      this.finish(active, { phase: "failed", error: message, message });
      logger.warn("youtube upload failed", {
        jobUid,
        status: errorStatus(error),
        error: message,
      });
    } finally {
      if (this.active === active) this.active = null;
    }
  }

  private async cancelJob(jobUid: string): Promise<void> {
    try {
      await this.api({
        method: "POST",
        path: `/publish/jobs/${encodeURIComponent(jobUid)}/cancel`,
        timeoutMs: 15_000,
      });
    } catch (error) {
      logger.warn("youtube upload: job cancel rejected", { jobUid, error: errorText(error) });
    }
  }

  private async report(input: {
    batchId: string;
    profileId: string;
    role: string;
    videoId: string;
    videoUrl: string | null;
    title: string;
    status: "success" | "failed";
    errorMessage?: string | null;
  }): Promise<void> {
    const body: Record<string, unknown> = {
      batch_id: input.batchId,
      profile_id: input.profileId,
      role: String(input.role ?? "").trim().toUpperCase() || "OK",
      video_id: input.videoId,
      video_url: input.videoUrl,
      title: input.title,
      status: input.status,
    };
    if (input.errorMessage) body.error_message = input.errorMessage;
    try {
      await this.api({ method: "POST", path: "/youtube/uploads/report", body, timeoutMs: 30_000 });
    } catch (error) {
      if (input.status === "success") {
        // The video is live; losing the bookkeeping write must be visible but
        // must not turn a successful publish into a failed one.
        logger.error("youtube upload: report failed after publish", { error: errorText(error) });
        return;
      }
      logger.warn("youtube upload: failure report rejected", { error: errorText(error) });
      return;
    }
    if (input.status === "success") {
      logger.info("youtube upload reported", { videoId: input.videoId });
    }
  }

  private patch(active: ActiveUpload, patch: Partial<YoutubeUploadState>): void {
    active.state = { ...active.state, ...patch };
    this.sync(active.state);
  }

  private progress(active: ActiveUpload, sentBytes: number, totalBytes: number): void {
    const total = Math.max(1, totalBytes);
    const sent = Math.max(0, Math.min(sentBytes, totalBytes));
    const percent = Math.min(100, Math.floor((sent * 100) / total));
    this.patch(active, {
      sentBytes: sent,
      totalBytes,
      percent,
      message: `Uploading to YouTube… ${percent}%`,
    });
  }

  private finish(active: ActiveUpload, patch: Partial<YoutubeUploadState>): void {
    active.state = { ...active.state, ...patch, finishedAt: this.now() };
    this.sync(active.state);
    if (this.active === active) this.active = null;
  }

  private push(state: YoutubeUploadState): void {
    this.history = [state, ...this.history.filter((item) => item.uploadId !== state.uploadId)].slice(
      0,
      this.historyLimit,
    );
    this.emit({ ...state });
  }

  private sync(state: YoutubeUploadState): void {
    this.history = this.history.map((item) =>
      item.uploadId === state.uploadId ? { ...state } : item,
    );
    this.emit({ ...state });
  }
}
