import type { SunoClient } from "./client.js";

/**
 * Serializable description of a job submission — the JSONB stored in
 * `jobs.payload` (migration 0012).
 *
 * A submission is normally a closure over a live `SunoClient`, which cannot be
 * written to a queue. A descriptor is the JSON form of that closure: a registry
 * key plus the arguments it needs, so any process can rebuild and run it.
 */
export interface JobDescriptor {
  /** Key into `JOB_OPS` identifying the operation to run. */
  op: string;
  /** JSON-serializable arguments for the operation (e.g. `{ id: "…" }`). */
  args?: Record<string, unknown>;
  /** Routing constraints that must survive a restart. */
  options?: { model?: string; policy?: string };
}

export interface JobOp {
  /**
   * `"result"` stores the return value as-is; `"clip"` polls the returned clips
   * to completion — the same split as `runResultJobWithRetry` /
   * `runClipJobWithRetry`.
   */
  mode: "result" | "clip";
  run: (client: SunoClient, args: Record<string, unknown>) => Promise<unknown>;
}

function str(args: Record<string, unknown>, key: string): string {
  const value = args[key];
  if (typeof value !== "string" || !value) {
    throw new Error(`Job descriptor is missing required argument "${key}".`);
  }
  return value;
}

/**
 * Ops whose submission is fully captured by JSON arguments. A job carrying one
 * of these descriptors can be rebuilt and re-run by any consumer after a crash,
 * which is what `recoverJobs()` relies on.
 *
 * Ops NOT listed here — the composite music/sounds/lyrics builders, whose input
 * is a whole request body shaped into a closure — keep the pre-R4 behaviour:
 * they run in the process that accepted the request and are failed out on
 * restart. Add entries here to bring them under the queue incrementally.
 */
export const JOB_OPS: Record<string, JobOp> = {
  // Clip-asset detail reads (`meDetailRoute` / `detailRoute`).
  stems_detail: { mode: "result", run: (c, a) => c.stemsDetail(str(a, "id")) },
  video_detail: { mode: "result", run: (c, a) => c.videoDetail(str(a, "id")) },
  cover_detail: { mode: "result", run: (c, a) => c.coverDetail(str(a, "id")) },
  subtitle_detail: { mode: "result", run: (c, a) => c.subtitleDetail(str(a, "id")) },
  recovery_detail: { mode: "result", run: (c, a) => c.recoveryDetail(str(a, "id")) },
  mp4_detail: { mode: "result", run: (c, a) => c.mp4Detail(str(a, "id")) },
  midi_detail: { mode: "result", run: (c, a) => c.midiDetail(str(a, "id")) },
  lyrics_detail: { mode: "result", run: (c, a) => c.getClipDetail(str(a, "id")) },
  timestamped_lyrics_detail: { mode: "result", run: (c, a) => c.lyricsDetail(str(a, "id")) },
  // Clip-id keyed operations.
  stems: { mode: "clip", run: (c, a) => c.stems(str(a, "id"), (a.mode as "vocal" | "stems" | "advanced") ?? "stems") },
  // Recovery re-signs an existing job's stored media and makes no Suno client
  // call, so runDescribedJob() handles it directly (getJob/ensureAudio). It is
  // registered here only so isRunnableDescriptor()/recoverJobs() treat it as
  // durable and re-queue it after a restart instead of failing it out.
  recovery_audio: {
    mode: "result",
    run: async () => {
      throw new Error("recovery_audio is handled directly by runDescribedJob.");
    },
  },
};

/** True when `value` is a descriptor this build knows how to run. */
export function isRunnableDescriptor(value: unknown): value is JobDescriptor {
  if (!value || typeof value !== "object") return false;
  return typeof (value as JobDescriptor).op === "string" && Boolean(JOB_OPS[(value as JobDescriptor).op]);
}
