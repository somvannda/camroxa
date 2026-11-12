"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Icon } from "@/components/Icon";

/**
 * First-run onboarding for an empty project (roadmap G18, reference spec §10).
 *
 * The reference opens a centred overlay offering ways to start: open a song from the
 * library, load the demo, upload audio, watch a tutorial, or start empty. We only
 * offer what this build can actually do — a tile that opens nothing would be worse
 * than no tile at all.
 */

const SEEN_PREFIX = "studio:onboarded:";

function seenKey(projectId: string): string {
  return `${SEEN_PREFIX}${projectId}`;
}

export function StudioOnboarding({
  projectId,
  isEmpty,
  reopenToken = 0,
}: {
  projectId: string | null;
  isEmpty: boolean;
  /** Increment to re-open the overlay ("Show Quick Start again" in the project menu). */
  reopenToken?: number;
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

  if (!open) return null;

  return (
    <div className="se-onboard-backdrop" role="dialog" aria-modal="true" aria-label="How do you want to start?">
      <div className="se-onboard">
        <h2>How do you want to start?</h2>
        <p className="se-onboard-sub">
          {isEmpty
            ? "This project is empty. Pick a starting point — you can always add more later."
            : "Pick a starting point — you can always add more later."}
        </p>

        <div className="se-onboard-tiles">
          <button type="button" className="se-onboard-tile" onClick={dismiss}>
            <Icon name="fa-table-columns" />
            <strong>Empty arrangement</strong>
            <span>Add a track and build from bar one.</span>
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
        </div>

        <div className="se-onboard-foot">
          <button type="button" className="se-pill on" onClick={dismiss}>
            Start empty
          </button>
        </div>
      </div>
    </div>
  );
}
