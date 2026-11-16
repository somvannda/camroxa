"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Icon } from "@/components/Icon";

/**
 * First-run onboarding for an empty project (roadmap G18, reference spec §10).
 *
 * The capture offers five ways to start (Edit Your Song · Drum & Bass Demo · Upload Audio ·
 * Video Tutorial · Empty Project) fanned across the editor, with a close ✕ and a "Browse
 * Studio projects ›" pill. We ship the four that do something real: edit a song from the
 * library, upload audio, create a song, and start empty. The demo tile needs a bundled demo
 * arrangement we do not have, and the video tutorial is the YouTube row dropped by product
 * decision (CLONE_DEFINITION §5) — both are recorded as sanctioned absences, not silent gaps.
 */

const SEEN_PREFIX = "studio:onboarded:";

function seenKey(projectId: string): string {
  return `${SEEN_PREFIX}${projectId}`;
}

export function StudioOnboarding({
  projectId,
  isEmpty,
  reopenToken = 0,
  onOpenLibrary,
}: {
  projectId: string | null;
  isEmpty: boolean;
  /** Increment to re-open the overlay ("Show Quick Start again" in the project menu). */
  reopenToken?: number;
  /** Open the library drawer on a specific list (songs or uploads). */
  onOpenLibrary?: (tab: "songs" | "uploads") => void;
}) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!projectId || !isEmpty) {
      setOpen(false);
      return;
    }
    try {
      setOpen(window.localStorage.getItem(seenKey(projectId)) !== "1");
    } catch {
      setOpen(true);
    }
  }, [projectId, isEmpty]);

  useEffect(() => {
    if (!projectId || reopenToken <= 0) return;
    // Re-opening clears the "seen" flag so the overlay is not a one-shot.
    try {
      window.localStorage.removeItem(seenKey(projectId));
    } catch {
      /* storage may be unavailable; the overlay still opens */
    }
    setOpen(true);
  }, [projectId, reopenToken]);

  function dismiss() {
    if (projectId) {
      try {
        window.localStorage.setItem(seenKey(projectId), "1");
      } catch {
        /* storage may be unavailable; the overlay still closes */
      }
    }
    setOpen(false);
  }

  function openLibrary(tab: "songs" | "uploads") {
    dismiss();
    onOpenLibrary?.(tab);
  }

  if (!open) return null;

  return (
    <div
      className="se-onboard-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="How do you want to start?"
    >
      <div className="se-onboard">
        <button
          type="button"
          className="se-dialog-x se-onboard-x"
          aria-label="Close"
          onClick={dismiss}
        >
          <Icon name="fa-xmark" />
        </button>
        <h2>How do you want to start?</h2>
        <p className="se-onboard-sub">
          {isEmpty
            ? "This project is empty. Pick a starting point — you can always add more later."
            : "Pick a starting point — you can always add more later."}
        </p>

        <div className="se-onboard-tiles">
          <button type="button" className="se-onboard-tile" onClick={() => openLibrary("songs")}>
            <Icon name="fa-music" />
            <strong>Edit Your Song</strong>
            <span>Open a song from your library.</span>
          </button>

          <button type="button" className="se-onboard-tile" onClick={() => openLibrary("uploads")}>
            <Icon name="fa-arrow-up-from-bracket" />
            <strong>Upload Audio</strong>
            <span>Bring in a file from your computer.</span>
          </button>

          <Link className="se-onboard-tile" href="/create">
            <Icon name="fa-wand-magic-sparkles" />
            <strong>Create a song</strong>
            <span>Generate audio, then bring it into a project.</span>
          </Link>

          <Link className="se-onboard-tile" href="/studio">
            <Icon name="fa-folder-open" />
            <strong>Open a project</strong>
            <span>Resume something you already started.</span>
          </Link>

          <button type="button" className="se-onboard-tile" onClick={dismiss}>
            <Icon name="fa-table-columns" />
            <strong>Empty Project</strong>
            <span>Add a track and build from bar one.</span>
          </button>
        </div>

        <div className="se-onboard-foot">
          <Link className="se-pill" href="/studio">
            Browse Studio projects ›
          </Link>
          <button type="button" className="se-pill on" onClick={dismiss}>
            Start empty
          </button>
        </div>
      </div>
    </div>
  );
}
