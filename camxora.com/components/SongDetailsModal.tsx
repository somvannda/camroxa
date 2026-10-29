"use client";

import { useState } from "react";

import { Icon } from "@/components/Icon";

/**
 * Suno's Edit ▸ Song Details: rename the version and edit the displayed
 * lyrics without regenerating the audio.
 */
export function SongDetailsModal({
  title,
  lyrics,
  busy = false,
  onClose,
  onSubmit,
}: {
  title: string;
  lyrics: string;
  busy?: boolean;
  onClose: () => void;
  onSubmit: (input: { title: string; lyrics: string }) => Promise<void> | void;
}) {
  const [nextTitle, setNextTitle] = useState(title);
  const [nextLyrics, setNextLyrics] = useState(lyrics);

  const canSave = nextTitle.trim().length > 0 && !busy;

  return (
    <div
      className="s-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Song details"
      onClick={onClose}
    >
      <div
        className="s-modal"
        style={{ width: "min(560px,100%)" }}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="s-modal-head">
          <h3>Song details</h3>
          <button
            type="button"
            className="s-btn s-btn-icon sm"
            aria-label="Close"
            onClick={onClose}
          >
            <Icon name="fa-xmark" />
          </button>
        </div>
        <div className="s-modal-body">
          <label className="s-note" htmlFor="song-details-title">
            Title
          </label>
          <input
            id="song-details-title"
            className="s-input"
            value={nextTitle}
            maxLength={200}
            onChange={(event) => setNextTitle(event.target.value)}
          />
          <label className="s-note" htmlFor="song-details-lyrics">
            Lyrics
          </label>
          <textarea
            id="song-details-lyrics"
            className="s-input"
            rows={10}
            value={nextLyrics}
            onChange={(event) => setNextLyrics(event.target.value)}
            placeholder="No lyrics — this track is instrumental."
          />
          <p className="s-note">
            Editing the lyrics changes what is shown and downloaded; the audio is
            not regenerated.
          </p>
        </div>
        <div className="s-modal-foot">
          <span style={{ flex: 1 }} />
          <button type="button" className="s-btn s-btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="s-btn s-btn-primary"
            disabled={!canSave}
            onClick={() =>
              void onSubmit({ title: nextTitle.trim(), lyrics: nextLyrics })
            }
          >
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
