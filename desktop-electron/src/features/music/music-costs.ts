import type { ChannelProfile, OperationCost } from "./music-types";

/** One Suno song package yields one track per channel (Primary + Secondary). */
export const TRACKS_PER_SONG_PACKAGE = 2;
/** Each album/channel is merged once. */
export const MERGE_OPS_PER_BATCH = 2;
/** One publish job per merged video. */
export const PUBLISH_OPS_PER_MERGE = 1;

export interface PlanCostInput {
  lyricCost?: OperationCost | null;
  musicCost?: OperationCost | null;
  imageCost?: OperationCost | null;
  titleCost?: OperationCost | null;
  albumCost?: OperationCost | null;
  videoCost?: OperationCost | null;
  mergeCost?: OperationCost | null;
  publishCost?: OperationCost | null;
  primary: ChannelProfile[];
  secondary: ChannelProfile[];
  songCount: number;
  autoGenImage: boolean;
  autoGSuno: boolean;
  autoVideo: boolean;
  autoMerge: boolean;
  autoReel: boolean;
  autoUpload: boolean;
  dayCount: number | null;
  imageSourceMode: "ai" | "manual";
}

export interface PlanCostBreakdown {
  dayCount: number;
  pairCount: number;
  batchCount: number;
  songCount: number;
  /** days × pairs × songs */
  songJobs: number;
  draftUnitCost: number | null;
  draftTotal: number | null;
  sunoUnitCost: number | null;
  sunoTotal: number | null;
  imageJobsPerDay: number;
  imageTotalJobs: number;
  imageUnitCost: number | null;
  imageTotal: number | null;
  videoOps: number;
  videoTotal: number | null;
  mergeOps: number;
  mergeTotal: number | null;
  uploadOps: number;
  uploadTotal: number | null;
  videoMergeTotal: number | null;
  total: number | null;
}

export function operationUnitCost(cost: OperationCost | null | undefined): number | null {
  if (!cost || cost.available === false || cost.credits_per_operation === null || cost.credits_per_operation === undefined) {
    return null;
  }
  return Number(cost.credits_per_operation);
}

export function formatCredits(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "unavailable";
  const rounded = Math.round(value * 100) / 100;
  return rounded.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

export function formatCreditLine(label: string, value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return `${label}: unavailable`;
  }
  return `${label}: ${formatCredits(value)} credits`;
}

export function formatButtonCredits(label: string, total: number | null): string {
  if (total === null) return label;
  return `${label} (${formatCredits(total)} credits)`;
}

/** Album image jobs per channel: one per mode; bg+thumb is the default. */
export function profileImageJobCount(profile: ChannelProfile | null | undefined): number {
  if (!profile) return 2;
  const mode = String(profile.image_config?.mode ?? "bg_thumb").trim().toLowerCase();
  return mode === "bg_only" || mode === "thumb_only" ? 1 : 2;
}

function imageJobsPerSong(primary: ChannelProfile[], secondary: ChannelProfile[]): number {
  return primary.reduce(
    (total, profile, index) =>
      total + profileImageJobCount(profile) + profileImageJobCount(secondary[index]),
    0,
  );
}

/**
 * Port of the 1.7.1 Electron cost model.
 *
 * Draft = lyric per song (+ title per song + album per batch when the backend
 * prices them). Album images are one BG/TH set per song per channel, which is
 * what the documented parity fixtures assert (4 songs = 16 jobs).
 */
export function planCostBreakdown(input: PlanCostInput): PlanCostBreakdown | null {
  const pairCount = input.primary.length;
  if (
    input.songCount <= 0 ||
    pairCount === 0 ||
    pairCount !== input.secondary.length ||
    input.dayCount === null ||
    input.dayCount <= 0
  ) {
    return null;
  }

  const batchCount = pairCount * input.dayCount;
  const songJobs = batchCount * input.songCount;

  const lyricUnit = operationUnitCost(input.lyricCost);
  const titleUnit = operationUnitCost(input.titleCost);
  const albumUnit = operationUnitCost(input.albumCost);

  let draftTotal: number | null = null;
  if (lyricUnit !== null) {
    if (titleUnit !== null && albumUnit !== null) {
      draftTotal = lyricUnit * songJobs + titleUnit * songJobs + albumUnit * batchCount;
    } else {
      draftTotal = lyricUnit * songJobs;
    }
  }

  const sunoUnit = operationUnitCost(input.musicCost);
  const sunoTotal = !input.autoGSuno ? 0 : sunoUnit === null ? null : sunoUnit * songJobs;

  const imageUnit = operationUnitCost(input.imageCost);
  const imagesBillable = input.autoGenImage && input.imageSourceMode !== "manual";
  const jobsPerDay = imageJobsPerSong(input.primary, input.secondary) * input.songCount;
  const imageTotalJobs = imagesBillable ? jobsPerDay * input.dayCount : 0;
  const imageTotal = !imagesBillable
    ? 0
    : imageUnit === null
      ? null
      : imageUnit * imageTotalJobs;

  const branches = input.autoReel ? 2 : 1;
  const videoBillable = input.autoVideo && input.autoGSuno;
  const mergeBillable = videoBillable && input.autoMerge;
  const videoOps = videoBillable ? songJobs * TRACKS_PER_SONG_PACKAGE * branches : 0;
  const mergeOps = mergeBillable ? batchCount * MERGE_OPS_PER_BATCH * branches : 0;

  const videoUnit = operationUnitCost(input.videoCost);
  const mergeUnit = operationUnitCost(input.mergeCost);
  const videoTotal = !videoBillable ? 0 : videoUnit === null ? null : videoUnit * videoOps;
  const mergeTotal = !mergeBillable ? 0 : mergeUnit === null ? null : mergeUnit * mergeOps;

  const publishUnit = operationUnitCost(input.publishCost);
  const uploadOps = input.autoUpload && mergeOps > 0 ? mergeOps * PUBLISH_OPS_PER_MERGE : 0;
  const uploadTotal =
    uploadOps <= 0 ? 0 : publishUnit === null ? null : publishUnit * uploadOps;

  const videoMergeTotal =
    videoBillable || mergeBillable
      ? videoTotal === null || mergeTotal === null
        ? null
        : videoTotal + mergeTotal
      : 0;

  const total =
    draftTotal === null ||
    sunoTotal === null ||
    imageTotal === null ||
    videoTotal === null ||
    mergeTotal === null ||
    uploadTotal === null
      ? null
      : draftTotal + sunoTotal + imageTotal + videoTotal + mergeTotal + uploadTotal;

  return {
    dayCount: input.dayCount,
    pairCount,
    batchCount,
    songCount: input.songCount,
    songJobs,
    draftUnitCost: lyricUnit,
    draftTotal,
    sunoUnitCost: sunoUnit,
    sunoTotal,
    imageJobsPerDay: jobsPerDay,
    imageTotalJobs,
    imageUnitCost: imageUnit,
    imageTotal,
    videoOps,
    videoTotal,
    mergeOps,
    mergeTotal,
    uploadOps,
    uploadTotal,
    videoMergeTotal,
    total,
  };
}

export function formatPlanLine(breakdown: PlanCostBreakdown | null): string {
  if (!breakdown) return "Select dates and matching channel pairs to estimate this run.";
  const dayLabel = breakdown.dayCount === 1 ? "day" : "days";
  const pairLabel = breakdown.pairCount === 1 ? "pair" : "pairs";
  const songLabel = breakdown.songCount === 1 ? "song" : "songs";
  return `${breakdown.dayCount} ${dayLabel} x ${breakdown.pairCount} ${pairLabel} x ${breakdown.songCount} ${songLabel} = ${breakdown.songJobs} song jobs`;
}

export function costByType(costs: OperationCost[] | null | undefined): Map<string, OperationCost> {
  const map = new Map<string, OperationCost>();
  for (const cost of costs ?? []) {
    if (cost && typeof cost.operation_type === "string") map.set(cost.operation_type, cost);
  }
  return map;
}
