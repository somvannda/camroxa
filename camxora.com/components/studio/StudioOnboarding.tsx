"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Icon } from "@/components/Icon";

/**
 * First-run onboarding for an empty project (roadmap G18, reference spec §10).
 *
 * The capture offers five ways to start (Edit Your Song · Drum & Bass Demo · Upload Audio ·
 * Video Tutorial · Empty Project) fanned across the editor, with a close ✕ and a "Browse
 * Studio projects ›" pill. We ship five tiles in that order: edit a song from the library,
 * the Drum & Bass demo (a project we seed with our own loop — the reference's bundled
 * multi-track arrangement is not ours to ship), upload audio, create a song and start
 * empty. The video tutorial is the YouTube row dropped by product decision
 * (CLONE_DEFINITION §5) — the one recorded absence, not a silent gap.
 */

const SEEN_PREFIX = "studio:onboarded:";

function seenKey(projectId: string): string {
  return `${SEEN_PREFIX}${projectId}`;
}

export function StudioOnboarding({
  projectId,
  isEmpty,
  loading = false,
  reopenToken = 0,
  onOpenLibrary,
  onOpenDemo,
}: {
  projectId: string | null;
  isEmpty: boolean;
  /** True while the document is still loading; the seen flag must not be set early. */
  loading?: boolean;
  /** Increment to re-open the overlay ("Show Quick Start again" in the project menu). */
  reopenToken?: number;
  /** Open the library drawer on a specific list (songs or uploads). */
  onOpenLibrary?: (tab: "songs" | "uploads") => void;
  /** Create and open the demo project (our own loop, seeded by `buildDemoProject`). */
  onOpenDemo?: () => void | Promise<void>;
}) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!projectId || loading) return;
    if (!isEmpty) {
      setOpen(false);
      // A project that has ever held clips is not a first run. Marking it seen keeps the
      // overlay from reopening when the user deletes the last clip (W5 bounce regression).
      if (projectId) {
        try {
          window.localStorage.setItem(seenKey(projectId), "1");
        } catch {
          /* storage may be unavailable */
        }
      }
      return;
    }
    try {
      setOpen(window.localStorage.getItem(seenKey(projectId)) !== "1");
    } catch {
      setOpen(true);
    }
  }, [projectId, isEmpty, loading]);

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

  async function openDemo() {
    if (!onOpenDemo) return;
    // Close first, like the library tiles: the editor is about to swap projects, and a
    // closed overlay cannot be clicked twice into a second demo project.
    dismiss();
    await onOpenDemo();
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

          <button
            type="button"
            className="se-onboard-tile"
            onClick={() => void openDemo()}
            disabled={!onOpenDemo}
          >
            <Icon name="fa-drum" />
            <strong>Drum &amp; Bass Demo</strong>
            <span>A finished track to play, poke at and pull apart.</span>
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
