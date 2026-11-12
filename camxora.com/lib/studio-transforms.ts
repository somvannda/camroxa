/**
 * Clip transforms (spec §16 / GEN-014…GEN-019): Extend, Cover and Remaster run through
 * the Studio operation API and land back on the arrangement.
 *
 * The reference's clip menu was never captured, so the shapes here are our decision
 * (D-033): a variant-style transform (Cover, Remaster) becomes a **take** on the source
 * clip, while Extend becomes a new clip after it. Kept pure so the placement rules are
 * testable without Web Audio or the API.
 */

export type OperationClipResult = {
  id?: string;
  title?: string;
  label?: string;
  audio_url?: string;
  durable_url?: string;
  durableUrl?: string;
  duration?: number;
  duration_seconds?: number | null;
};

export type ClipTake = {
  id: string;
  title?: string;
  audioUrl?: string | null;
  duration?: number;
  active?: boolean;
};

export type TakeHost = {
  id: string;
  duration?: number;
  audioUrl?: string | null;
  takes?: ClipTake[];
  /** Audio before the first transform, kept so "Heal Edits" can restore it. */
  sourceAudioUrl?: string | null;
  sourceDuration?: number;
};

/** The URL a result clip should actually play from. */
export function resultAudioUrl(result: OperationClipResult): string | null {
  return result.durable_url ?? result.durableUrl ?? result.audio_url ?? null;
}

export function resultDuration(
  result: OperationClipResult,
  fallback = 8
): number {
  const value = result.duration_seconds ?? result.duration;
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : fallback;
}

/**
 * Add a transform result as the active take of a clip. The previous takes are kept (the
 * take lanes are the history), and the clip's audio follows the new active take so
 * playback and export hear it immediately.
 */
export function withTransformTake<T extends TakeHost>(
  clip: T,
  label: string,
  result: OperationClipResult,
  stamp: string
): T & { takes: ClipTake[]; sourceAudioUrl?: string | null; sourceDuration?: number } {
  const url = resultAudioUrl(result);
  const take: ClipTake = {
    id: `${clip.id}-${stamp}`,
    title: label,
    audioUrl: url,
    duration: resultDuration(result, clip.duration),
    active: true,
  };
  const prior = (clip.takes ?? []).map((entry) => ({ ...entry, active: false }));
  return {
    ...clip,
    sourceAudioUrl: clip.sourceAudioUrl ?? clip.audioUrl ?? null,
    sourceDuration: clip.sourceDuration ?? clip.duration,
    takes: [take, ...prior],
    ...(url ? { audioUrl: url } : {}),
  } as T & { takes: ClipTake[]; sourceAudioUrl?: string | null; sourceDuration?: number };
}

/**
 * "Heal Edits": drop every generated take and restore the audio/duration the clip had
 * before its first transform. Clips with no transform history are returned unchanged.
 */
export function healClipEdits<T extends TakeHost>(clip: T): T {
  if (!clip.takes?.length && !clip.sourceAudioUrl) return clip;
  return {
    ...clip,
    audioUrl: clip.sourceAudioUrl ?? clip.audioUrl,
    duration: clip.sourceDuration ?? clip.duration,
    takes: [],
    sourceAudioUrl: null,
    sourceDuration: undefined,
  };
}

/** Where an extended clip starts: immediately after its source. */
export function extendedClipStart(source: { start?: number; duration?: number }): number {
  return Math.max(0, (source.start ?? 0) + (source.duration ?? 0));
}
