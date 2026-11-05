"use client";

import { forwardRef } from "react";

import { Icon } from "@/components/Icon";
import type { WebMusicGeneration } from "@/lib/library-api";
import type { StudioProject, StudioUpload } from "@/lib/studio-api";

/**
 * Library panel: songs from the generation library (with Add), other Studio
 * projects (with Open) and imported audio uploads (with Add). Extracted from the
 * shell (roadmap G15); it owns no state so the lists can be fetched and refreshed
 * elsewhere.
 *
 * Reference shape note (spec §19.1): the reference's panel is two-level — four
 * filter tiles (All Songs / Liked / Stems / Uploads), then workspaces and projects,
 * then a dated song list. We present the same material as flat tabs until the
 * workspace API exists; "Stems" stays out because a stem set cannot be listed
 * before a stems job has succeeded (blocker B-005).
 */

export type StudioLibraryTab = "songs" | "projects" | "uploads";

export type StudioLibraryProps = {
  width: number;
  tab: StudioLibraryTab;
  onTab: (tab: StudioLibraryTab) => void;
  query: string;
  onQuery: (value: string) => void;
  songs: WebMusicGeneration[] | null;
  projects: StudioProject[] | null;
  uploads: StudioUpload[] | null;
  currentProjectId: string | null;
  onClose: () => void;
  onAddSong: (song: WebMusicGeneration) => void;
  onAddUpload: (upload: StudioUpload) => void;
  onOpenProject: (projectId: string) => void;
};

const TABS: { value: StudioLibraryTab; label: string }[] = [
  { value: "songs", label: "Songs" },
  { value: "projects", label: "Projects" },
  { value: "uploads", label: "Uploads" },
];

/** "2:07" for a known length, "—" when the upload did not report one. */
export function formatUploadLength(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds <= 0) return "—";
  const total = Math.round(seconds);
  const minutes = Math.floor(total / 60);
  return `${minutes}:${String(total % 60).padStart(2, "0")}`;
}

export const StudioLibrary = forwardRef<HTMLInputElement, StudioLibraryProps>(
  function StudioLibrary(props, searchRef) {
    const {
      width,
      tab,
      onTab,
      query,
      onQuery,
      songs,
      projects,
      uploads,
      currentProjectId,
      onClose,
      onAddSong,
      onAddUpload,
      onOpenProject,
    } = props;

    const q = query.trim().toLowerCase();
    const visibleSongs = (songs ?? []).filter((song) =>
      q ? `${song.title} ${song.style ?? ""}`.toLowerCase().includes(q) : true
    );
    const otherProjects = (projects ?? [])
      .filter((item) => item.id !== currentProjectId)
      .filter((item) => (q ? item.title.toLowerCase().includes(q) : true));
    const visibleUploads = (uploads ?? []).filter((upload) =>
      q ? upload.filename.toLowerCase().includes(q) : true
    );

    return (
      <aside className="se-library" aria-label="Library" style={{ width }}>
        <div className="se-library-head">
          <strong>Library</strong>
          <input
            ref={searchRef}
            className="se-lib-search"
            value={query}
            onChange={(event) => onQuery(event.target.value)}
            placeholder="Search library"
            aria-label="Search library"
          />
          <button type="button" className="se-icon" onClick={onClose} aria-label="Close library">
            <Icon name="fa-xmark" />
          </button>
        </div>

        <div className="se-lib-tabs" role="tablist" aria-label="Library sections">
          {TABS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={tab === value}
              className={`se-lib-tab${tab === value ? " on" : ""}`}
              onClick={() => onTab(value)}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "songs" ? (
          songs === null ? (
            <p className="se-lib-empty">Loading songs…</p>
          ) : songs.length === 0 ? (
            <p className="se-lib-empty">No songs yet. Create one, then drop it onto a track here.</p>
          ) : (
            <ul className="se-lib-list">
              {visibleSongs.map((song) => (
                <li key={song.id} className="se-lib-row">
                  <span className="se-lib-title">{song.title || "Untitled song"}</span>
                  <span className="se-lib-meta">{song.style?.slice(0, 44) || "No style"}</span>
                  <button
                    type="button"
                    className="se-pill"
                    onClick={() => onAddSong(song)}
                    disabled={!song.clips?.some((clip) => clip.audio_url)}
                  >
                    Add
                  </button>
                </li>
              ))}
            </ul>
          )
        ) : tab === "projects" ? (
          projects === null ? (
            <p className="se-lib-empty">Loading projects…</p>
          ) : otherProjects.length === 0 ? (
            <p className="se-lib-empty">No other projects yet.</p>
          ) : (
            <ul className="se-lib-list">
              {otherProjects.map((item) => (
                <li key={item.id} className="se-lib-row">
                  <span className="se-lib-title">{item.title}</span>
                  <span className="se-lib-meta">
                    {item.bpm} BPM · {item.time_signature || "4/4"}
                  </span>
                  <button type="button" className="se-pill" onClick={() => onOpenProject(item.id)}>
                    Open
                  </button>
                </li>
              ))}
            </ul>
          )
        ) : uploads === null ? (
          <p className="se-lib-empty">Loading uploads…</p>
        ) : uploads.length === 0 ? (
          <p className="se-lib-empty">No uploads yet. Audio you import appears here.</p>
        ) : (
          <ul className="se-lib-list">
            {visibleUploads.map((upload) => (
              <li key={upload.id} className="se-lib-row">
                <span className="se-lib-title">{upload.filename}</span>
                <span className="se-lib-meta">{formatUploadLength(upload.duration_seconds)}</span>
                <button
                  type="button"
                  className="se-pill"
                  onClick={() => onAddUpload(upload)}
                  disabled={!upload.url}
                  aria-label={`Add ${upload.filename}`}
                >
                  Add
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>
    );
  }
);
