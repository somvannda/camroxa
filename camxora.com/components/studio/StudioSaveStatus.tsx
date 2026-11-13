"use client";

/**
 * Autosave status surface (roadmap W2.1).
 *
 * The reference has none of this: it autosaves silently and, when two tabs collide,
 * says nothing (§93). We are deliberately diverging — a DAW that eats a take without
 * telling anyone is worse than one that admits it failed.
 *
 * States:
 *   saved   — everything is on the server
 *   saving  — a write is in flight
 *   error   — the last write failed; the chip becomes the retry button
 *   offline — no connection; the change is queued in the browser until it returns
 */

export type SaveStatus = "saved" | "saving" | "error" | "offline";

/** Mirror state shown next to the save chip; never includes Suno credentials. */
export type SaveSyncState = {
  status: "pending" | "linked" | "synced" | "conflict" | "error";
  last_error: string | null;
  skipped_clips?: string[];
  state_sync: boolean;
};

const LABEL: Record<SaveStatus, string> = {
  saved: "Saved",
  saving: "Saving…",
  error: "Save failed · Retry",
  offline: "Offline · changes not saved",
};

const SYNC_TITLE: Record<SaveSyncState["status"], string> = {
  pending: "Suno Studio: waiting for the first copy",
  linked: "Suno Studio: project exists — arrangement mirroring is staged",
  synced: "Suno Studio: mirrored",
  conflict: "Suno Studio has newer changes",
  error: "Suno Studio sync failed",
};

export function StudioSaveStatus({
  status,
  onRetry,
  sync,
}: {
  status: SaveStatus;
  onRetry?: () => void;
  sync?: SaveSyncState | null;
}) {
  const dot = sync ? (
    <span
      className="se-sync-dot"
      data-state={sync.status}
      role="img"
      aria-label={SYNC_TITLE[sync.status]}
      title={
        sync.last_error
          ? `${SYNC_TITLE[sync.status]}: ${sync.last_error}`
          : sync.skipped_clips?.length
            ? `${SYNC_TITLE[sync.status]}: ${sync.skipped_clips.length} clip(s) have no Suno copy yet.`
            : sync.status === "linked" && !sync.state_sync
              ? `${SYNC_TITLE[sync.status]}: arrangement writes are paused.`
              : SYNC_TITLE[sync.status]
      }
    />
  ) : null;

  if (status === "saved") {
    return (
      <span className="se-pill se-save" aria-live="polite" title="All changes saved">
        {LABEL.saved}
        {dot}
      </span>
    );
  }

  if (status === "error") {
    return (
      <button
        type="button"
        className="se-pill se-save on"
        onClick={onRetry}
        aria-live="polite"
        title="The last change could not be saved. Click to retry."
      >
        {LABEL.error}
        {dot}
      </button>
    );
  }

  return (
    <span className="se-pill se-save on" aria-live="polite">
      {LABEL[status]}
      {dot}
    </span>
  );
}
