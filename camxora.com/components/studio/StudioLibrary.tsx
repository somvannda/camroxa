"use client";

import { forwardRef } from "react";

import { Icon } from "@/components/Icon";
import type { WebMusicGeneration } from "@/lib/library-api";
import { groupByDay } from "@/lib/studio-library-grouping";
import type { WebMusicWorkspace } from "@/lib/web-music-api";
import type { StudioProject, StudioUpload } from "@/lib/studio-api";

/**
 * Library panel: songs from the generation library (with Add), the workspaces that
 * group them, other Studio projects (with Open) and imported audio uploads (with Add).
 * Extracted from the shell (roadmap G15); it owns no state so the lists can be fetched
 * and refreshed elsewhere.
 *
 * Reference shape note (spec §19.1): the reference is two-level — filter tiles
 * (All Songs / Liked / Stems / Uploads), workspaces and projects, then a dated song
 * list for the chosen workspace. We keep one drawer with tabs: choosing a workspace
 * here switches to Songs filtered to it, which is the same two-level flow without the
 * tile grid. "Stems" and "Liked" stay out: a stem set cannot be listed before a stems
 * job succeeds (B-005), and the like keys we store are per clip, not a song corpus.
 */

export type StudioLibraryTab = "songs" | "workspaces" | "projects" | "uploads";

export type StudioLibraryProps = {
  width: number;
  tab: StudioLibraryTab;
  onTab: (tab: StudioLibraryTab) => void;
  query: string;
  onQuery: (value: string) => void;
  songs: WebMusicGeneration[] | null;
  workspaces: WebMusicWorkspace[] | null;
  activeWorkspaceId: string | null;
  projects: StudioProject[] | null;
  uploads: StudioUpload[] | null;
  currentProjectId: string | null;
  onClose: () => void;
  onAddSong: (song: WebMusicGeneration) => void;
  onSelectWorkspace: (workspaceId: string | null) => void;
  onAddUpload: (upload: StudioUpload) => void;
  onOpenProject: (projectId: string) => void;
};

const TABS: { value: StudioLibraryTab; label: string }[] = [
  { value: "songs", label: "Songs" },
  { value: "workspaces", label: "Workspaces" },
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

/** "946 songs" / "1 song"; the reference shows the count next to each workspace. */
export function formatSongCount(count: number | null | undefined): string {
  const value = Math.max(0, Math.round(Number(count) || 0));
  return `${value} ${value === 1 ? "song" : "songs"}`;
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
      workspaces,
      activeWorkspaceId,
      projects,
      uploads,
      currentProjectId,
      onClose,
      onAddSong,
      onSelectWorkspace,
      onAddUpload,
      onOpenProject,
    } = props;

    const q = query.trim().toLowerCase();
    const activeWorkspace = (workspaces ?? []).find((item) => item.id === activeWorkspaceId) ?? null;
    const visibleSongs = (songs ?? []).filter((song) =>
      q ? `${song.title} ${song.style ?? ""}`.toLowerCase().includes(q) : true
    );
    const otherProjects = (projects ?? [])
      .filter((item) => item.id !== currentProjectId)
      .filter((item) => (q ? item.title.toLowerCase().includes(q) : true));
    const visibleUploads = (uploads ?? []).filter((upload) =>
      q ? upload.filename.toLowerCase().includes(q) : true
    );
    const visibleWorkspaces = (workspaces ?? []).filter((workspace) =>
      q ? workspace.name.toLowerCase().includes(q) : true
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
          <>
            {activeWorkspace ? (
              <ul className="se-lib-list">
                <li className="se-lib-row">
                  <span className="se-lib-title">{activeWorkspace.name}</span>
                  <span className="se-lib-meta">workspace filter</span>
                  <button
                    type="button"
                    className="se-pill"
                    onClick={() => onSelectWorkspace(null)}
                    aria-label="Clear workspace filter"
                  >
                    Clear
                  </button>
                </li>
              </ul>
            ) : null}
            {songs === null ? (
              <p className="se-lib-empty">Loading songs…</p>
            ) : songs.length === 0 ? (
              <p className="se-lib-empty">
                {activeWorkspace
                  ? "No songs in this workspace yet."
                  : "No songs yet. Create one, then drop it onto a track here."}
              </p>
            ) : (
              <ul className="se-lib-list">
                {groupByDay(visibleSongs).map((group) => (
                  <li key={group.label} className="se-lib-day" aria-label={group.label}>
                    <span>{group.label}</span>
                    <ul>
                      {group.items.map((song) => (
                        <li key={song.id} className="se-lib-row">
                          <span className="se-lib-title">{song.title || "Untitled song"}</span>
                          <span className="se-lib-meta">
                            {song.style?.slice(0, 44) || "No style"}
                          </span>
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
                  </li>
                ))}
              </ul>
            )}
          </>
        ) : tab === "workspaces" ? (
          workspaces === null ? (
            <p className="se-lib-empty">Loading workspaces…</p>
          ) : workspaces.length === 0 ? (
            <p className="se-lib-empty">No workspaces yet.</p>
          ) : (
            <ul className="se-lib-list">
              <li className="se-lib-row">
                <span className="se-lib-title">All songs</span>
                <span className="se-lib-meta">every workspace</span>
                <button
                  type="button"
                  className="se-pill"
                  onClick={() => onSelectWorkspace(null)}
                  aria-label="Show songs from every workspace"
                >
                  Open
                </button>
              </li>
              {visibleWorkspaces.map((workspace) => (
                <li key={workspace.id} className="se-lib-row">
                  <span className="se-lib-title">{workspace.name}</span>
                  <span className="se-lib-meta">{formatSongCount(workspace.song_count)}</span>
                  <button
                    type="button"
                    className="se-pill"
                    onClick={() => onSelectWorkspace(workspace.id)}
                    aria-label={`Show songs in ${workspace.name}`}
                    aria-current={workspace.id === activeWorkspaceId}
                  >
                    Open
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
