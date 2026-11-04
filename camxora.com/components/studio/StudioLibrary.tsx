"use client";

import { forwardRef } from "react";

import { Icon } from "@/components/Icon";
import type { WebMusicGeneration } from "@/lib/library-api";
import type { StudioProject } from "@/lib/studio-api";

/**
 * Library panel: songs from the generation library (with Add) and other Studio
 * projects (with Open). Extracted from the shell (roadmap G15); it owns no state so
 * the two lists can be fetched and refreshed elsewhere.
 */

export type StudioLibraryProps = {
  width: number;
  tab: "songs" | "projects";
  onTab: (tab: "songs" | "projects") => void;
  query: string;
  onQuery: (value: string) => void;
  songs: WebMusicGeneration[] | null;
  projects: StudioProject[] | null;
  currentProjectId: string | null;
  onClose: () => void;
  onAddSong: (song: WebMusicGeneration) => void;
  onOpenProject: (projectId: string) => void;
};

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
      currentProjectId,
      onClose,
      onAddSong,
      onOpenProject,
    } = props;

    const q = query.trim().toLowerCase();
    const visibleSongs = (songs ?? []).filter((song) =>
      q ? `${song.title} ${song.style ?? ""}`.toLowerCase().includes(q) : true
    );
    const otherProjects = (projects ?? [])
      .filter((item) => item.id !== currentProjectId)
      .filter((item) => (q ? item.title.toLowerCase().includes(q) : true));

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
          {(["songs", "projects"] as const).map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={tab === value}
              className={`se-lib-tab${tab === value ? " on" : ""}`}
              onClick={() => onTab(value)}
            >
              {value === "songs" ? "Songs" : "Projects"}
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
        ) : projects === null ? (
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
        )}
      </aside>
    );
  }
);
