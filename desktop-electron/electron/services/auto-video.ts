/**
 * Auto-video candidate selection.
 *
 * Pure logic for the background coordinator: given the Progress rows, the
 * Music history, channel profiles, local templates and the durable queue, pick
 * the next branch that is ready to render. No Electron, no filesystem access —
 * the coordinator injects the background resolver and enqueues the result.
 *
 * The rules mirror the Python desktop:
 * - only rows with completed MP3 downloads and a real branch background;
 * - only profiles with a template for that branch;
 * - long and reel are independent (a checked branch may render on its own);
 * - a completed or failed local branch is not restarted automatically.
 */
import type { PipelineBranch } from "./pipeline-queue";

export type AutoVideoBranch = PipelineBranch;

export interface AutoVideoMeta {
  batch_id: string;
  profile_id: string;
  role: string;
  run_dir?: string | null;
  background_16x9_path?: string | null;
  background_9x16_path?: string | null;
  expected?: number;
  saved?: number;
  download_pending?: number;
  download_ready?: number;
  long_ready?: boolean;
  reel_ready?: boolean;
  pipeline_complete?: boolean;
  updated_at?: string | null;
}

export interface AutoVideoProgressRow {
  batch: string;
  run_date: string;
  meta: AutoVideoMeta;
}

export interface AutoVideoHistorySong {
  title?: string | null;
  album?: string | null;
  output_dir_ok?: string | null;
  output_dir_alt?: string | null;
  downloaded_ok?: boolean;
  downloaded_alt?: boolean;
}

export interface AutoVideoHistoryBatch {
  batch_id: string;
  ok_album?: string | null;
  alt_album?: string | null;
  songs?: AutoVideoHistorySong[];
}

export interface AutoVideoProfile {
  id: string;
  name?: string | null;
  video_template_id?: string | null;
  reel_template_id?: string | null;
}

export interface AutoVideoTemplate {
  id: string;
  kind: AutoVideoBranch;
}

export interface AutoVideoLocalJob {
  batchId: string;
  branch: AutoVideoBranch;
  status: "queued" | "rendering" | "encoding" | "merging" | "done" | "failed" | "cancelled";
}

export interface AutoVideoSwitches {
  /** Video (16:9) */
  long: boolean;
  /** Video (9:16) */
  reel: boolean;
  /** Merge Video */
  merge: boolean;
}

export interface AutoVideoJob {
  branch: AutoVideoBranch;
  templateId: string;
  audioDir: string;
  audioBranch: "ok" | "alt";
  title: string;
  artist: string;
  album: string;
  backgroundPath: string;
}

export interface AutoVideoCandidate {
  /** Progress row key: batch + profile + role. */
  key: string;
  externalBatchId: string;
  /** Pipeline-local batch id; one per branch so long and reel never merge together. */
  pipelineBatchId: string;
  branch: AutoVideoBranch;
  templateId: string;
  outputDir: string;
  backgroundPath: string;
  merge: boolean;
  jobs: AutoVideoJob[];
}

export interface AutoVideoSelectInput {
  settings: AutoVideoSwitches;
  rows: AutoVideoProgressRow[];
  batches: AutoVideoHistoryBatch[];
  profiles: AutoVideoProfile[];
  templates: AutoVideoTemplate[];
  localJobs: AutoVideoLocalJob[];
  /** Returns a readable absolute background file, or null when it is not ready. */
  resolveBackground: (row: AutoVideoProgressRow, branch: AutoVideoBranch) => string | null;
}

/** One durable pipeline batch per branch; merging cannot mix long and reel. */
export function autoPipelineBatchId(externalBatchId: string, branch: AutoVideoBranch): string {
  const base = externalBatchId.trim() || "batch";
  return `${base}:${branch}`;
}

function clean(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function roleSide(role: string): "ok" | "alt" | null {
  const key = clean(role).toLowerCase();
  if (key === "ok" || key === "primary") return "ok";
  if (key === "alt" || key === "secondary") return "alt";
  return null;
}

function songIsReady(song: AutoVideoHistorySong, side: "ok" | "alt"): boolean {
  const dir = clean(side === "ok" ? song.output_dir_ok : song.output_dir_alt);
  if (!dir) return false;
  const downloaded = side === "ok" ? song.downloaded_ok : song.downloaded_alt;
  return downloaded !== false;
}

function songTitle(song: AutoVideoHistorySong): string {
  return clean(song.title);
}

function branchTemplate(
  profile: AutoVideoProfile | undefined,
  branch: AutoVideoBranch,
): string {
  return clean(
    branch === "long" ? profile?.video_template_id : profile?.reel_template_id,
  );
}

function localBranchState(
  jobs: AutoVideoLocalJob[],
  pipelineBatchId: string,
  branch: AutoVideoBranch,
  expectedRenders: number,
): "absent" | "running" | "done" | "blocked" | "partial" {
  const branchJobs = jobs.filter(
    (job) => job.batchId === pipelineBatchId && job.branch === branch,
  );
  if (branchJobs.length === 0) return "absent";
  if (branchJobs.some((job) => job.status === "failed" || job.status === "cancelled")) {
    return "blocked";
  }
  if (
    branchJobs.some(
      (job) =>
        job.status === "queued" ||
        job.status === "rendering" ||
        job.status === "encoding" ||
        job.status === "merging",
    )
  ) {
    return "running";
  }
  if (!branchJobs.every((job) => job.status === "done")) return "running";
  return branchJobs.length >= Math.max(1, expectedRenders) ? "done" : "partial";
}

export function selectAutoVideoCandidate(
  input: AutoVideoSelectInput,
): AutoVideoCandidate | null {
  if (!input.settings.long && !input.settings.reel) return null;

  const batches = new Map(input.batches.map((batch) => [clean(batch.batch_id), batch]));
  const profiles = new Map(input.profiles.map((profile) => [clean(profile.id), profile]));
  const templates = new Map(
    input.templates.map((template) => [`${clean(template.id)}|${template.kind}`, template]),
  );

  const rows = [...input.rows].sort((left, right) => {
    const leftAt = clean(left.meta.updated_at) || left.run_date;
    const rightAt = clean(right.meta.updated_at) || right.run_date;
    return rightAt.localeCompare(leftAt);
  });

  for (const row of rows) {
    const meta = row.meta;
    if (meta.pipeline_complete) continue;
    const externalBatchId = clean(meta.batch_id) || clean(row.batch);
    if (!externalBatchId) continue;
    const runDir = clean(meta.run_dir);
    if (!runDir) continue;

    const side = roleSide(meta.role);
    if (!side) continue;

    const profile = profiles.get(clean(meta.profile_id));
    if (!profile) continue;

    const batch = batches.get(externalBatchId);
    if (!batch) continue;

    const songs = (batch.songs ?? []).filter((song) => songIsReady(song, side));
    if (songs.length === 0) continue;

    const expected = Math.max(1, Number(meta.expected) || songs.length);
    if (songs.length < expected) continue;
    if ((Number(meta.download_pending) || 0) > 0) continue;
    const saved = Number(meta.saved);
    if (Number.isFinite(saved) && saved < expected) continue;
    const ready = Number(meta.download_ready);
    if (Number.isFinite(ready) && ready < expected) continue;

    const branches: AutoVideoBranch[] = [];
    if (input.settings.long) branches.push("long");
    if (input.settings.reel) branches.push("reel");

    for (const branch of branches) {
      const done = branch === "long" ? meta.long_ready === true : meta.reel_ready === true;
      if (done) continue;

      const pipelineBatchId = autoPipelineBatchId(externalBatchId, branch);
      const state = localBranchState(
        input.localJobs,
        pipelineBatchId,
        branch,
        songs.length,
      );
      if (state === "running" || state === "done" || state === "blocked") continue;

      const templateId = branchTemplate(profile, branch);
      if (!templateId) continue;
      if (!templates.has(`${templateId}|${branch}`)) continue;

      const backgroundPath = input.resolveBackground(row, branch);
      if (!backgroundPath) continue;

      const artist = clean(profile.name);
      const batchAlbum =
        clean(side === "ok" ? batch.ok_album : batch.alt_album) ||
        clean(batch.ok_album) ||
        clean(batch.alt_album) ||
        clean(batch.songs?.[0]?.album);

      const jobs: AutoVideoJob[] = songs.map((song) => ({
        branch,
        templateId,
        audioDir: clean(side === "ok" ? song.output_dir_ok : song.output_dir_alt),
        audioBranch: side,
        title: songTitle(song),
        artist,
        album: batchAlbum || clean(song.album),
        backgroundPath,
      }));

      return {
        key: `${externalBatchId}:${clean(meta.profile_id)}:${clean(meta.role)}`,
        externalBatchId,
        pipelineBatchId,
        branch,
        templateId,
        outputDir: runDir,
        backgroundPath,
        merge: input.settings.merge,
        jobs,
      };
    }
  }

  return null;
}
