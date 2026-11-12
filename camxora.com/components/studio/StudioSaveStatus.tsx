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

const LABEL: Record<SaveStatus, string> = {
  saved: "Saved",
  saving: "Saving…",
  error: "Save failed · Retry",
  offline: "Offline · changes not saved",
};

export function StudioSaveStatus({
  status,
  onRetry,
}: {
  status: SaveStatus;
  onRetry?: () => void;
}) {
  if (status === "saved") {
    return (
      <span className="se-pill se-save" aria-live="polite" title="All changes saved">
        {LABEL.saved}
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
      </button>
    );
  }

  return (
    <span className="se-pill se-save on" aria-live="polite">
      {LABEL[status]}
    </span>
  );
}
