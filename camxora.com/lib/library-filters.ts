/**
 * Library feed filters.
 *
 * The reference exposes a wide filter set (`filterCovers`, `filterUploadedClips`,
 * `filterPrivateClips`, …). Our corpus only carries some of it, so the menu is honest:
 * filters backed by data are live, the rest stay visible with a stated reason. This
 * module is the single place that decides what a filter means, so the menu and the row
 * matching cannot drift.
 */

export type LibraryFilterId =
  | "liked"
  | "disliked"
  | "public"
  | "private"
  | "uploads"
  | "full"
  | "cover"
  | "voice"
  | "instrumental"
  | "downloads"
  | "hideDisliked"
  | "hideStems";

export type LibraryFilterRow = {
  liked: boolean;
  disliked: boolean;
  /** The clip has playable audio (its package finished). */
  ready: boolean;
  /** Clip length in seconds; 0 when unknown. */
  duration: number;
  /** The song was generated without vocals. */
  instrumental: boolean;
};

export type LibraryFilterOption = {
  id: LibraryFilterId;
  label: string;
  /** Why the filter cannot work yet; absent for live filters. */
  reason?: string;
  /** Selected by default when nothing else is on. */
  defaultOn?: boolean;
};

export const LIBRARY_FILTERS: LibraryFilterOption[] = [
  { id: "liked", label: "Liked" },
  { id: "disliked", label: "Disliked" },
  { id: "public", label: "Public", reason: "Songs stay private; publishing is not built yet." },
  { id: "private", label: "Private", reason: "Every song is private today, so this filter cannot narrow anything." },
  { id: "uploads", label: "Uploads", reason: "Uploaded audio has its own tab." },
  { id: "full", label: "Full song" },
  {
    id: "cover",
    label: "Cover",
    reason: "Covers create new versions; the corpus does not record which versions came from a cover.",
  },
  { id: "voice", label: "Vocals" },
  { id: "instrumental", label: "Instrumental" },
  { id: "downloads", label: "Ready to play" },
  { id: "hideDisliked", label: "Hide disliked" },
  { id: "hideStems", label: "Hide stems", reason: "The library lists songs; stems live in Studio." },
];

/** True when the row passes every active filter. */
export function matchesLibraryFilters(
  row: LibraryFilterRow,
  active: readonly LibraryFilterId[]
): boolean {
  if (active.length === 0) return true;
  if (active.includes("hideDisliked") && row.disliked) return false;
  if (active.includes("liked") && !row.liked) return false;
  if (active.includes("disliked") && !row.disliked) return false;
  if (active.includes("downloads") && !row.ready) return false;
  if (active.includes("full") && row.duration > 0 && row.duration < 60) return false;
  if (active.includes("voice") && row.instrumental) return false;
  if (active.includes("instrumental") && !row.instrumental) return false;
  return true;
}
