/**
 * Asset extraction, shared by job finalization, ownership recording and the
 * sunoapi.org-shaped record-info responses.
 *
 * Two id namespaces are owned the same way:
 *   - clip ids — any object carrying a string `id` plus at least one media URL;
 *   - upload-session ids — the `{ id, url, fields }` shape returned by
 *     `upload/init`.
 * Results nest differently across job types (`[{ clips: [...] }]`, a bare
 * object, `sunoData[]`), so one recursive collector keeps every caller in step.
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

/** The upload-session id from an `upload/init`-shaped result, or null. */
export function extractUploadSessionId(value: unknown): string | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const o = value as Record<string, unknown>;
  if (
    typeof o.id === "string" &&
    o.id &&
    typeof o.url === "string" &&
    o.fields != null &&
    typeof o.fields === "object"
  ) {
    return o.id;
  }
  return null;
}

/** Distinct owned asset ids (clips plus any upload-session id) in a job result. */
export function extractOwnedAssetIds(value: unknown): string[] {
  const ids = new Set<string>(extractClipIds(value));
  const uploadId = extractUploadSessionId(value);
  if (uploadId) ids.add(uploadId);
  return [...ids];
}
