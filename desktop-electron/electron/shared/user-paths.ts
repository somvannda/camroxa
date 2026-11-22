/**
 * Resolve a path that came from the platform API.
 *
 * The backend stores portable, machine-relative run keys such as
 * `bass-drive\2026-11-22_Letters-Against-the-Moon` and relative image
 * outputs. On the desktop those paths belong under the configured Suno output
 * folder (the same root the download coordinator uses), never under the app's
 * working directory.
 */
import path from "node:path";

/** Pure resolver; `base` must be absolute. */
export function resolveUnderBase(value: string, base: string): string {
  const raw = String(value ?? "").trim();
  if (!raw) return raw;
  if (path.isAbsolute(raw)) return path.normalize(raw);
  const root = String(base ?? "").trim();
  if (!root) return raw;
  return path.resolve(root, raw);
}
