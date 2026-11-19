/**
 * Pure helpers for the manual YouTube upload surfaces (PG-20 / PG-50).
 *
 * The main process owns the truth (merged file, channel, quota, token); these
 * functions only decide what the row, table cell and confirmation dialog show,
 * so every branch stays unit-testable without Electron.
 */
import type {
  YoutubeAvailability,
  YoutubeChannelSummary,
  YoutubePlaylistOption,
  YoutubeUploadRowState,
  YoutubeUploadState,
} from "../../../electron/shared/types";
import { localVideoState, rowKey, stageKey } from "./progress-format";
import type { ProgressRow } from "./progress-types";

export const AUTO_UPLOAD_NOTE =
  "Auto-Upload stays off, exactly as in 1.7.1. Nothing uploads until you click Upload to YouTube.";

export function uploadRowQuery(row: ProgressRow): {
  key: string;
  batchId: string;
  profileId: string;
  role: string;
  runDir: string | null;
  youtubeUrl: string | null;
} | null {
  const batchId = String(row.meta.batch_id || row.batch || "").trim();
  const profileId = String(row.meta.profile_id ?? "").trim();
  if (!batchId || !profileId) return null;
  return {
    key: rowKey(row),
    batchId,
    profileId,
    role: String(row.meta.role ?? "OK").trim() || "OK",
    runDir: row.meta.run_dir ? String(row.meta.run_dir) : null,
    youtubeUrl: row.meta.youtube_url ? String(row.meta.youtube_url) : null,
  };
}

/**
 * Rows worth asking the main process about: anything that reached a video
 * output, a run folder or the YouTube stage. Early music/image rows are not
 * polled for upload readiness.
 */
export function uploadCandidateRows(rows: ProgressRow[]): ProgressRow[] {
  return rows.filter((row) => {
    if (!uploadRowQuery(row)) return false;
    const key = stageKey(row.stage);
    if (key === "youtube" || key === "done" || key === "completed" || key === "error") return true;
    if (row.meta.pipeline_complete || row.meta.long_ready || row.meta.reel_ready) return true;
    if (row.meta.run_dir) return true;
    return localVideoState(row).merge !== null;
  });
}

export function isUploadCandidate(row: ProgressRow): boolean {
  const key = stageKey(row.stage);
  if (key === "youtube" || key === "done" || key === "completed") return true;
  if (row.meta.pipeline_complete || row.meta.long_ready || row.meta.reel_ready) return true;
  return localVideoState(row).merge !== null;
}

export function availabilitySignature(rows: ProgressRow[]): string {
  return uploadCandidateRows(rows)
    .map((row) => {
      const query = uploadRowQuery(row);
      return [
        query?.key ?? "",
        row.meta.youtube_url ?? "",
        row.meta.youtube_status ?? "",
        row.meta.run_dir ?? "",
      ].join("~");
    })
    .join("|");
}

export function availabilityFor(
  availability: YoutubeAvailability | null,
  key: string,
): YoutubeUploadRowState | undefined {
  return availability?.rows.find((item) => item.key === key);
}

/** The newest attempt for a row, finished or running. */
export function latestUploadFor(
  history: YoutubeUploadState[],
  key: string,
): YoutubeUploadState | undefined {
  return history.find((item) => item.key === key);
}

export function formatUploadBytes(bytes: number | null | undefined): string {
  const value = Number(bytes ?? 0);
  if (!Number.isFinite(value) || value <= 0) return "0 MB";
  if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024))} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  return `${(value / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function formatUploadProgress(state: YoutubeUploadState | null | undefined): string {
  if (!state) return "";
  const sent = formatUploadBytes(state.sentBytes);
  const total = formatUploadBytes(state.totalBytes);
  return `${state.percent}% · ${sent} of ${total}`;
}

export type UploadTone = "neutral" | "success" | "warning" | "danger" | "accent";

export function uploadTone(state: YoutubeUploadState | null | undefined): UploadTone {
  switch (state?.phase) {
    case "uploading":
    case "preparing":
    case "recording":
    case "queued":
      return "accent";
    case "done":
      return "success";
    case "failed":
      return "danger";
    case "cancelled":
      return "warning";
    default:
      return "neutral";
  }
}

export function uploadPhaseLabel(state: YoutubeUploadState | null | undefined): string {
  switch (state?.phase) {
    case "queued":
      return "Queued";
    case "preparing":
      return "Preparing";
    case "uploading":
      return "Uploading";
    case "recording":
      return "Recording";
    case "done":
      return "Uploaded";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Cancelled";
    default:
      return "Not started";
  }
}

export interface UploadControlState {
  /** The main-process verdict for this row, when loaded. */
  row: YoutubeUploadRowState | undefined;
  /** Newest attempt for this row. */
  upload: YoutubeUploadState | undefined;
  channel: YoutubeChannelSummary | null;
  /** True while another row's upload owns the single upload slot. */
  blockedByOther: boolean;
  /** Set when the availability lookup itself failed. */
  lookupError: string | null;
}

export interface UploadControl {
  canUpload: boolean;
  /** Shown when the action is disabled; never empty for a disabled control. */
  reason: string | null;
  uploading: boolean;
  canCancel: boolean;
  canRetry: boolean;
  playlistId: string;
  playlistLabel: string | null;
  videoUrl: string | null;
}

const BLOCK_REASONS: Record<string, string> = {
  "no-file": "No merged video for this run yet.",
  "no-channel": "YouTube is not connected for this channel.",
  "no-token": "YouTube did not return an access token. Reconnect the channel.",
  quota: "The daily YouTube upload quota is reached.",
  plan: "This upload needs a paid plan or more credits.",
  "legacy-template": "This channel still uses a legacy Camxora template.",
  "already-uploaded": "This video is already on YouTube.",
  uploading: "This video is uploading now.",
  busy: "Another upload is running.",
  unavailable: "Upload details could not be loaded.",
};

export function blockLabel(block: string | undefined): string {
  return (block && BLOCK_REASONS[block]) || "Upload is unavailable.";
}

export function uploadControl(input: UploadControlState): UploadControl {
  const { row, upload, channel } = input;
  const uploading = upload?.phase === "uploading" || upload?.phase === "preparing" || upload?.phase === "queued" || upload?.phase === "recording";
  const failed = upload?.phase === "failed";
  const videoUrl = upload?.videoUrl ?? null;

  let canUpload = false;
  let reason: string | null = null;

  if (input.lookupError) {
    reason = `Upload readiness could not be checked. ${input.lookupError}`;
  } else if (!row) {
    reason = "Checking the merged video and channel…";
  } else if (uploading) {
    reason = null;
  } else if (upload?.phase === "done" && videoUrl) {
    reason = "This video is already on YouTube. Open the link above to view it.";
  } else if (row.block === "none") {
    canUpload = true;
  } else if (row.block === "already-uploaded") {
    reason = "This video is already on YouTube.";
  } else {
    reason = row.reason ?? blockLabel(row.block);
  }

  if (canUpload && !channel?.connected) {
    canUpload = false;
    reason = "YouTube is not connected for this channel. Connect it in Settings → Profiles.";
  }
  if (canUpload && input.blockedByOther) {
    canUpload = false;
    reason = "Another YouTube upload is running. Wait for it to finish or cancel it.";
  }

  return {
    canUpload,
    reason,
    uploading,
    canCancel: uploading,
    canRetry: failed && Boolean(row?.mergedPath),
    playlistId: channel?.playlistId ?? "",
    playlistLabel: channel?.playlistTitle ?? null,
    videoUrl,
  };
}

export function playlistOptions(channel: YoutubeChannelSummary | null): YoutubePlaylistOption[] {
  return channel?.playlists ?? [];
}

/** `With playlist` is offered only when the channel really has one. */
export function playlistChoices(
  channel: YoutubeChannelSummary | null,
  planPlaylistId?: string | null,
): Array<{ value: string; label: string }> {
  const options = playlistOptions(channel);
  const choices: Array<{ value: string; label: string }> = [];
  const fallbackId = String(planPlaylistId ?? channel?.playlistId ?? "").trim();
  if (fallbackId) {
    const title =
      channel?.playlistTitle ??
      options.find((item) => item.id === fallbackId)?.title ??
      fallbackId;
    choices.push({ value: fallbackId, label: `${title} (profile default)` });
  }
  for (const option of options) {
    if (choices.some((choice) => choice.value === option.id)) continue;
    choices.push({ value: option.id, label: option.title });
  }
  choices.push({ value: "none", label: "No playlist" });
  return choices;
}

/** Disclosure lines for the confirmation dialog, in reading order. */
export function confirmationLines(input: {
  channelTitle: string | null;
  profileName: string | null;
  title: string;
  visibility: string;
  mergedName: string;
  mergedBytes: number;
  playlistTitle: string | null;
  containsSyntheticMedia: boolean;
  madeForKids: boolean;
}): Array<{ label: string; value: string }> {
  return [
    {
      label: "Channel",
      value: input.channelTitle
        ? input.profileName && input.profileName !== input.channelTitle
          ? `${input.channelTitle} (${input.profileName})`
          : input.channelTitle
        : input.profileName || "Connected channel",
    },
    { label: "Title", value: input.title },
    { label: "Visibility", value: input.visibility },
    { label: "File", value: `${input.mergedName} · ${formatUploadBytes(input.mergedBytes)}` },
    { label: "Playlist", value: input.playlistTitle || "None" },
    {
      label: "Disclosure",
      value: input.containsSyntheticMedia
        ? input.madeForKids
          ? "AI-generated · made for kids"
          : "AI-generated content disclosed"
        : input.madeForKids
          ? "Made for kids"
          : "Not marked as AI-generated",
    },
  ];
}
