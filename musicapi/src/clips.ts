/**
 * Clip extraction, shared by job finalization, ownership recording and the
 * sunoapi.org-shaped record-info responses.
 *
 * A "clip" is any object carrying a string `id` plus at least one media URL.
 * Results nest clips differently across job types (`[{ clips: [...] }]`, a bare
 * object, `sunoData[]`), so a single recursive collector keeps every caller in
 * agreement.
 */

/** Flatten a job/usage result into its individual clip-like objects. */
export function collectClipObjects(value: unknown, out: Array<Record<string, unknown>>): void {
  if (Array.isArray(value)) {
    for (const v of value) collectClipObjects(v, out);
    return;
  }
  if (!value || typeof value !== "object") return;
  const o = value as Record<string, unknown>;
  const id = typeof o.id === "string" ? o.id : undefined;
  const clipLike = Boolean(
    id && (o.media_urls || o.audio_url || o.audioUrl || o.image_url || o.imageUrl || o.video_url),
  );
  if (clipLike) out.push(o);
  if (Array.isArray(o.clips)) collectClipObjects(o.clips, out);
  if (Array.isArray(o.data)) collectClipObjects(o.data, out);
  if (Array.isArray(o.sunoData)) collectClipObjects(o.sunoData, out);
}

/** Distinct clip ids present in a job/usage result. */
export function extractClipIds(value: unknown): string[] {
  const out: Array<Record<string, unknown>> = [];
  collectClipObjects(value, out);
  const ids = new Set<string>();
  for (const clip of out) {
    if (typeof clip.id === "string" && clip.id) ids.add(clip.id);
  }
  return [...ids];
}
