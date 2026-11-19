import type {
  PipelineEnqueueJob,
  PipelineEnqueueRequest,
} from "../../../electron/shared/types";
import type { ChannelProfile, MusicHistoryBatch, MusicHistorySong } from "./music-types";

/**
 * Builds the video-pipeline request from what the Music page already knows.
 *
 * No path is invented here: a song is only queued when the backend recorded a
 * run folder for it and the download is marked done. The main process resolves
 * the actual audio file inside that folder (`pipeline-sources.ts`) and reports
 * a specific reason when it cannot — the queue stays empty instead of pointing
 * at a guessed file.
 */
export interface MusicPipelineOptions {
  profiles: ChannelProfile[];
  /** Channel profiles selected in the composer; empty means "any". */
  primaryIds: string[];
  /** History batches, newest first, as the Music page shows them. */
  batches: MusicHistoryBatch[];
  /** Settings fallback when a profile has no template of its own. */
  videoTemplateId: string;
  reelTemplateId: string;
  merge: boolean;
  reel: boolean;
}

export interface MusicPipelinePlan {
  request: PipelineEnqueueRequest | null;
  /** Distinct songs with at least one queued job. */
  songCount: number;
  jobCount: number;
  /** User-facing template problems; a Settings link is shown with them. */
  templateErrors: string[];
  /** Songs that have no renderable audio yet. */
  audioErrors: string[];
  /** Honest one-line summary for the Automation card. */
  message: string;
  /** Batch the jobs belong to (undefined when nothing is queued). */
  batchId: string | null;
}

function clean(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export function songIsReady(song: MusicHistorySong): boolean {
  return (
    song.downloaded_ok === true ||
    Boolean(clean(song.output_dir_ok) || clean(song.output_dir_alt))
  );
}

export function buildMusicPipelinePlan(options: MusicPipelineOptions): MusicPipelinePlan {
  const templateErrors: string[] = [];
  const audioErrors: string[] = [];
  const jobs: PipelineEnqueueJob[] = [];
  const jobKeys = new Set<string>();
  const songsWithJobs = new Set<string>();
  let sawBatch = false;
  let batchId: string | null = null;
  let outputDir = "";

  const selected = new Set(options.primaryIds.filter(Boolean));
  const profileById = new Map(options.profiles.map((profile) => [profile.id, profile]));

  const templateFor = (profile: ChannelProfile | undefined, branch: "long" | "reel"): string => {
    const own = clean(branch === "long" ? profile?.video_template_id : profile?.reel_template_id);
    const fallback = clean(branch === "long" ? options.videoTemplateId : options.reelTemplateId);
    return own || fallback;
  };

  for (const batch of options.batches) {
    const sides: Array<{ side: "ok" | "alt"; profileId: string }> = [
      { side: "ok", profileId: clean(batch.ok_profile_id) },
      { side: "alt", profileId: clean(batch.alt_profile_id) },
    ].filter((entry) => entry.profileId) as Array<{ side: "ok" | "alt"; profileId: string }>;
    if (sides.length === 0) continue;
    sawBatch = true;

    const batchJobs: PipelineEnqueueJob[] = [];
    const batchSongs = new Set<string>();
    let batchDir = "";

    for (const song of batch.songs ?? []) {
      if (!songIsReady(song)) continue;
      const title = clean(song.title);
      const songKey = `${song.song_id}:${title}`;
      for (const { side, profileId } of sides) {
        if (selected.size > 0 && !selected.has(profileId)) continue;
        const profile = profileById.get(profileId);
        const dir = clean(side === "ok" ? song.output_dir_ok : song.output_dir_alt);
        if (!dir) {
          if (title) audioErrors.push(`${title}: the run folder is not set.`);
          continue;
        }
        const longTemplate = templateFor(profile, "long");
        if (!longTemplate) {
          const label = profile?.name ?? profileId;
          const text = `No long-video template is selected for ${label}. Choose one in Settings.`;
          if (!templateErrors.includes(text)) templateErrors.push(text);
          continue;
        }
        const base = {
          templateId: longTemplate,
          audioDir: dir,
          audioBranch: side,
          title,
          artist: "",
          album: clean(song.album),
        };
        batchJobs.push({ branch: "long", ...base });
        if (options.reel) {
          const reelTemplate = templateFor(profile, "reel");
          if (!reelTemplate) {
            const label = profile?.name ?? profileId;
            const text = `No reel template is selected for ${label}. Choose one in Settings, or turn Auto-Reel off.`;
            if (!templateErrors.includes(text)) templateErrors.push(text);
          } else {
            batchJobs.push({ branch: "reel", ...base, templateId: reelTemplate });
          }
        }
        batchSongs.add(songKey);
        if (!batchDir) batchDir = dir;
      }
    }

    if (batchJobs.length > 0) {
      batchId = clean(batch.batch_id) || null;
      outputDir = batchDir;
      for (const job of batchJobs) {
        const key = `${job.branch}|${job.templateId}|${job.audioDir}|${job.title}`;
        if (jobKeys.has(key)) continue;
        jobKeys.add(key);
        jobs.push(job);
      }
      for (const key of batchSongs) songsWithJobs.add(key);
      // Only the newest batch with ready songs is queued: history stays history.
      break;
    }
  }

  const message = (() => {
    if (jobs.length > 0) {
      const parts = [`${jobs.length} render${jobs.length === 1 ? "" : "s"} ready`];
      if (options.merge) parts.push("merge on");
      parts.push("Auto-Upload stays manual");
      return parts.join(" · ");
    }
    if (templateErrors.length > 0) return templateErrors[0];
    if (audioErrors.length > 0) return audioErrors[0];
    if (!sawBatch) {
      return "No finished batch to render yet. Generate a batch, then come back when the songs are downloaded.";
    }
    return "No songs are ready to render yet. Wait for the Suno downloads to finish.";
  })();

  const request: PipelineEnqueueRequest | null =
    jobs.length > 0 && batchId
      ? {
          batchId,
          outputDir,
          merge: options.merge,
          mergeName: `${batchId}-merged`,
          jobs,
        }
      : null;

  return {
    request,
    songCount: songsWithJobs.size,
    jobCount: jobs.length,
    templateErrors,
    audioErrors,
    message,
    batchId: request ? batchId : null,
  };
}
