"use client";

import { forwardRef, useRef, useState } from "react";

import { Icon } from "@/components/Icon";
import type { WebMusicGeneration } from "@/lib/library-api";
import { groupByDay, relativeAge } from "@/lib/studio-library-grouping";
import type { WebMusicWorkspace } from "@/lib/web-music-api";
import type { StudioProject, StudioUpload } from "@/lib/studio-api";

/**
 * Library panel (spec §19.1/§19.2): two levels, like the reference.
 *
 * Level 1 is the corpus chooser — All Songs / Liked / Stems / Uploads tiles, then the
 * Workspaces and Studio Projects sections (four rows each, with See all). Level 2 is the
 * list itself: songs grouped under Today / Yesterday / date headings, with the captured
 * toolbar (filter / + New / upload / In Project / Stems), or the uploads.
 *
 * Stems stays visible but disabled: a stem set cannot be listed before a stems job has
 * succeeded (B-005), so a control that opens nothing would be worse than a labelled one.
 */

export type SongFilter = "all" | "liked" | "project";

export type LibraryView =
  | { kind: "root" }
  | { kind: "songs"; title: string; filter: SongFilter }
  | { kind: "uploads" };

export type StudioLibraryProps = {
  width: number;
  view: LibraryView;
  query: string;
  onQuery: (value: string) => void;
  songs: WebMusicGeneration[] | null;
  workspaces: WebMusicWorkspace[] | null;
  activeWorkspaceId: string | null;
  projects: StudioProject[] | null;
  uploads: StudioUpload[] | null;
  currentProjectId: string | null;
  /** Clip keys the viewer liked (`<songId>:<variant>`), or null while loading. */
  likedKeys: string[] | null;
  /** Song id currently auditioning, or null. */
  playingSongId: string | null;
  /** Upload id currently auditioning, or null. */
  playingUploadId: string | null;
  /** Song ids the open project already uses, for the In Project filter. */
  projectSongIds: string[];
  /** Double-clicking a row opens its detail rail (§100). */
  onOpenSong: (song: WebMusicGeneration) => void;
  /** Failed library request, surfaced with a retry instead of an empty list. */
  error?: string | null;
  onRetry?: () => void;
  onClose: () => void;
  onBack: () => void;
  onOpenSongs: (filter: "all" | "liked") => void;
  onOpenUploads: () => void;
  onOpenWorkspace: (workspaceId: string | null) => void;
  onFilter: (filter: SongFilter) => void;
  /** "+ New" opens the generator (§19.2 toolbar). */
  onNewSong: () => void;
  /** Import an audio file into the library (§19.2 toolbar upload). */
  onUploadAudio: (file: File) => Promise<void>;
  /** Create a workspace from the captured level-1 row. */
  onNewWorkspace: () => Promise<void>;
  onAddSong: (song: WebMusicGeneration) => void;
  /** Audition button (reference rows have Play/Pause). */
  onTogglePlay: (song: WebMusicGeneration) => void;
  /** Like button (reference rows have Like); nextLiked is the requested state. */
  onToggleLike: (song: WebMusicGeneration, nextLiked: boolean) => void;
  /** Audition an upload (reference uploads rows have Play). */
  onToggleUploadPlay: (upload: StudioUpload) => void;
  onAddUpload: (upload: StudioUpload) => void;
  onOpenProject: (projectId: string) => void;
};

const ROOT_ROWS = 4;

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

/** The variant the Add button would place, or the first one when none is ready. */
export function primaryClip(song: WebMusicGeneration) {
  return (song.clips ?? []).find((clip) => clip.audio_url) ?? (song.clips ?? [])[0] ?? null;
}

/**
 * Tag strip under a song title (§19.2): version/model, variant, length. Key and tempo
 * are shown by the reference but are not part of our generation payload, so they are
 * absent instead of guessed.
 */
export function songTags(song: WebMusicGeneration): string[] {
  const clip = primaryClip(song);
  const tags: string[] = [];
  if (song.model_label) tags.push(song.model_label);
  if (clip?.label && clip.label.length <= 12) tags.push(clip.label);
  else if (clip?.variant) tags.push(clip.variant);
  if (clip?.duration_seconds) tags.push(formatUploadLength(clip.duration_seconds));
  return tags;
}

/** First letter of a name, for the artwork fallback. */
export function initialOf(name: string | null | undefined): string {
  return (name ?? "").trim().charAt(0).toUpperCase() || "?";
}

/** Data-transfer type for dragging a library song onto a track lane. */
export const SONG_DRAG_TYPE = "application/x-camxora-studio-song";

export const StudioLibrary = forwardRef<HTMLInputElement, StudioLibraryProps>(
  function StudioLibrary(props, searchRef) {
    const {
      width,
      view,
      query,
      onQuery,
      songs,
      workspaces,
      activeWorkspaceId,
      projects,
      uploads,
      currentProjectId,
      likedKeys,
      playingSongId,
      playingUploadId,
      projectSongIds,
      error,
      onRetry,
      onOpenSong,
      onClose,
      onBack,
      onOpenSongs,
      onOpenUploads,
      onOpenWorkspace,
      onFilter,
      onNewSong,
      onNewWorkspace,
      onUploadAudio,
      onAddSong,
      onTogglePlay,
      onToggleLike,
      onToggleUploadPlay,
      onAddUpload,
      onOpenProject,
    } = props;

    const [allWorkspaces, setAllWorkspaces] = useState(false);
    const [allProjects, setAllProjects] = useState(false);
    /** Date headings collapse their group, like the reference's heading buttons. */
    const [collapsedDays, setCollapsedDays] = useState<string[]>([]);
    const [uploading, setUploading] = useState(false);
    const [creatingWorkspace, setCreatingWorkspace] = useState(false);
    const [workspaceError, setWorkspaceError] = useState("");
    const [uploadError, setUploadError] = useState("");
    const fileRef = useRef<HTMLInputElement | null>(null);

    const q = query.trim().toLowerCase();
    const liked = new Set(likedKeys ?? []);
    const inProject = new Set(projectSongIds);
    const isLiked = (song: WebMusicGeneration) =>
      (song.clips ?? []).some((clip) => liked.has(`${song.id}:${clip.variant}`));

    const activeWorkspace = (workspaces ?? []).find((item) => item.id === activeWorkspaceId) ?? null;
    const filter: SongFilter = view.kind === "songs" ? view.filter : "all";
    const visibleSongs = (songs ?? [])
      .filter((song) =>
        view.kind === "songs" && view.filter === "liked"
          ? isLiked(song)
          : view.kind === "songs" && view.filter === "project"
            ? inProject.has(song.id)
            : true
      )
      .filter((song) => (q ? `${song.title} ${song.style ?? ""}`.toLowerCase().includes(q) : true));
    const otherProjects = (projects ?? [])
      .filter((item) => item.id !== currentProjectId)
      .filter((item) => (q ? item.title.toLowerCase().includes(q) : true));
    const visibleUploads = (uploads ?? []).filter((upload) =>
      q ? upload.filename.toLowerCase().includes(q) : true
    );
    const visibleWorkspaces = (workspaces ?? []).filter((workspace) =>
      q ? workspace.name.toLowerCase().includes(q) : true
    );

    async function importFile(file: File | undefined | null) {
      if (!file) return;
      setUploadError("");
      setUploading(true);
      try {
        await onUploadAudio(file);
      } catch (cause) {
        setUploadError(cause instanceof Error ? cause.message : "Upload failed.");
      } finally {
        setUploading(false);
        if (fileRef.current) fileRef.current.value = "";
      }
    }

    const uploadControl = (
      <>
        <input
          ref={fileRef}
          type="file"
          accept="audio/*"
          className="se-sr-only"
          aria-label="Choose audio file"
          onChange={(event) => void importFile(event.target.files?.[0])}
        />
        <button
          type="button"
          className="se-lib-tool"
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
          aria-label="Upload audio"
        >
          <Icon name="fa-arrow-up-from-bracket" />
          <span>{uploading ? "Uploading…" : "Upload"}</span>
        </button>
      </>
    );

    return (
      <aside className="se-library" aria-label="Library" style={{ width }}>
        <div className="se-library-head">
          {view.kind === "root" ? (
            <strong>Library</strong>
          ) : (
            <button type="button" className="se-icon" aria-label="Back to library" onClick={onBack}>
              <Icon name="fa-chevron-left" />
            </button>
          )}
          {view.kind !== "root" ? (
            <strong>{view.kind === "songs" ? view.title : "Uploads"}</strong>
          ) : null}
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

        {error ? (
          <p className="se-lib-error" role="alert">
            <span>{error}</span>
            <button type="button" className="se-pill" onClick={onRetry}>
              Retry
            </button>
          </p>
        ) : null}

        {view.kind === "root" ? (
          <div className="se-lib-root">
            <div className="se-lib-tiles" role="group" aria-label="Library filters">
              <button type="button" className="se-lib-tile" onClick={() => onOpenSongs("all")}>
                <span className="se-lib-tile-icon" data-tone="songs"><Icon name="fa-music" /></span>
                <span>All Songs</span>
              </button>
              <button type="button" className="se-lib-tile" onClick={() => onOpenSongs("liked")}>
                <span className="se-lib-tile-icon" data-tone="liked"><Icon name="fa-heart" /></span>
                <span>Liked</span>
              </button>
              <button
                type="button"
                className="se-lib-tile"
                disabled
                title="Stems need a finished stem separation first"
              >
                <span className="se-lib-tile-icon" data-tone="stems"><Icon name="fa-layer-group" /></span>
                <span>Stems</span>
              </button>
              <button type="button" className="se-lib-tile" onClick={onOpenUploads}>
                <span className="se-lib-tile-icon" data-tone="uploads"><Icon name="fa-arrow-up-from-bracket" /></span>
                <span>Uploads</span>
              </button>
            </div>

            <section className="se-lib-section" aria-label="Workspaces">
              <div className="se-lib-section-head">
                <strong>Workspaces</strong>
                {(workspaces?.length ?? 0) > ROOT_ROWS ? (
                  <button
                    type="button"
                    className="se-lib-seeall"
                    onClick={() => setAllWorkspaces((value) => !value)}
                  >
                    {allWorkspaces ? "Show less" : "See all ›"}
                  </button>
                ) : null}
              </div>
              <button
                type="button"
                className="se-lib-new"
                onClick={() => {
                  setWorkspaceError("");
                  setCreatingWorkspace(true);
                  void onNewWorkspace()
                    .catch((cause) => {
                      setWorkspaceError(
                        cause instanceof Error ? cause.message : "Could not create a workspace."
                      );
                    })
                    .finally(() => setCreatingWorkspace(false));
                }}
                disabled={creatingWorkspace}
              >
                <Icon name="fa-plus" />
                <span>{creatingWorkspace ? "Creating…" : "New workspace"}</span>
              </button>
              {workspaceError ? (
                <p className="se-lib-empty" role="alert">
                  {workspaceError}
                </p>
              ) : null}
              {workspaces === null ? (
                <p className="se-lib-empty">Loading workspaces…</p>
              ) : visibleWorkspaces.length === 0 ? (
                <p className="se-lib-empty">No workspaces yet.</p>
              ) : (
                <ul className="se-lib-list">
                  {(allWorkspaces ? visibleWorkspaces : visibleWorkspaces.slice(0, ROOT_ROWS)).map(
                    (workspace, index) => (
                      <li key={workspace.id}>
                        <div
                          className="se-lib-row se-lib-row-button"
                          aria-current={workspace.id === activeWorkspaceId}
                        >
                          <span
                            className={`se-lib-thumb se-lib-thumb-${index % 4}`}
                            aria-hidden="true"
                          >
                            {initialOf(workspace.name)}
                          </span>
                          <span className="se-lib-title">{workspace.name}</span>
                          <span className="se-lib-meta">
                            {formatSongCount(workspace.song_count)}
                          </span>
                          <button
                            type="button"
                            className="se-lib-row-action"
                            onClick={() => onOpenWorkspace(workspace.id)}
                            aria-label={`Open ${workspace.name}`}
                          >
                            Open
                          </button>
                        </div>
                      </li>
                    )
                  )}
                </ul>
              )}
            </section>

            <section className="se-lib-section" aria-label="Studio projects">
              <div className="se-lib-section-head">
                <strong>Studio Projects</strong>
                {otherProjects.length > ROOT_ROWS ? (
                  <button
                    type="button"
                    className="se-lib-seeall"
                    onClick={() => setAllProjects((value) => !value)}
                  >
                    {allProjects ? "Show less" : "See all ›"}
                  </button>
                ) : null}
              </div>
              {projects === null ? (
                <p className="se-lib-empty">Loading projects…</p>
              ) : otherProjects.length === 0 ? (
                <p className="se-lib-empty">No other projects yet.</p>
              ) : (
                <ul className="se-lib-list">
                  {(allProjects ? otherProjects : otherProjects.slice(0, ROOT_ROWS)).map((item) => (
                    <li key={item.id}>
                      <div className="se-lib-row se-lib-row-button">
                        <span className="se-lib-thumb se-lib-thumb-project" aria-hidden="true">
                          <Icon name="fa-bars-staggered" />
                        </span>
                        <span className="se-lib-title">{item.title}</span>
                        <span className="se-lib-meta">
                          {relativeAge(item.updated_at || item.created_at) || "—"}
                        </span>
                        <button
                          type="button"
                          className="se-lib-row-action"
                          onClick={() => onOpenProject(item.id)}
                          aria-label={`Open ${item.title}`}
                        >
                          Open
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        ) : view.kind === "songs" ? (
          <>
            <div className="se-lib-tools" role="toolbar" aria-label="Song filters">
              <button
                type="button"
                className={`se-lib-chip${filter === "liked" ? " on" : ""}`}
                aria-label="Liked only"
                aria-pressed={filter === "liked"}
                onClick={() => onFilter(filter === "liked" ? "all" : "liked")}
              >
                <Icon name="fa-heart" />
              </button>
              <button type="button" className="se-lib-chip" onClick={onNewSong}>
                <Icon name="fa-plus" />
                <span>New</span>
              </button>
              <button
                type="button"
                className={`se-lib-chip${filter === "project" ? " on" : ""}`}
                aria-pressed={filter === "project"}
                onClick={() => onFilter(filter === "project" ? "all" : "project")}
              >
                In Project
              </button>
              <button
                type="button"
                className="se-lib-chip"
                disabled
                title="Stems need a finished stem separation first"
              >
                Stems
              </button>
              <button type="button" className="se-lib-chip" onClick={onOpenUploads}>
                Uploads
              </button>
            </div>
            {activeWorkspace ? (
              <ul className="se-lib-list">
                <li className="se-lib-row">
                  <span className="se-lib-title">Workspace filter</span>
                  <span className="se-lib-meta">{activeWorkspace.name}</span>
                  <button
                    type="button"
                    className="se-pill"
                    onClick={() => onOpenWorkspace(null)}
                    aria-label="Clear workspace filter"
                  >
                    Clear
                  </button>
                </li>
              </ul>
            ) : null}
            {songs === null ? (
              <p className="se-lib-empty">Loading songs…</p>
            ) : visibleSongs.length === 0 ? (
              <p className="se-lib-empty">
                {view.filter === "liked"
                  ? "No liked songs yet."
                  : view.filter === "project"
                    ? "No songs from this project in the library yet."
                    : activeWorkspace
                      ? "No songs in this workspace yet."
                      : "No songs yet. Create one, then drop it onto a track here."}
              </p>
            ) : (
              <ul className="se-lib-list">
                {groupByDay(visibleSongs).map((group) => (
                  <li key={group.label} className="se-lib-day" aria-label={group.label}>
                    <button
                      type="button"
                      className="se-lib-day-head"
                      aria-expanded={!collapsedDays.includes(group.label)}
                      onClick={() =>
                        setCollapsedDays((previous) =>
                          previous.includes(group.label)
                            ? previous.filter((label) => label !== group.label)
                            : [...previous, group.label]
                        )
                      }
                    >
                      <span>{group.label}</span>
                      <span aria-hidden="true">
                        {collapsedDays.includes(group.label) ? "›" : "⌄"}
                      </span>
                    </button>
                    {collapsedDays.includes(group.label) ? null : (
                      <ul>
                        {group.items.map((song) => {
                        const clip = primaryClip(song);
                        const tags = songTags(song);
                        return (
                          <li
                            key={song.id}
                            className="se-lib-row se-lib-song"
                            draggable
                            tabIndex={0}
                            onKeyDown={(event) => {
                              if (event.target !== event.currentTarget) return;
                              if (event.key === "Enter") {
                                event.preventDefault();
                                onOpenSong(song);
                              }
                            }}
                            onDoubleClick={() => onOpenSong(song)}
                            onDragStart={(event) => {
                              event.dataTransfer.setData(SONG_DRAG_TYPE, song.id);
                              event.dataTransfer.effectAllowed = "copy";
                            }}
                          >
                            <span className="se-lib-art" aria-hidden="true">
                              {clip?.image_url ? (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img src={clip.image_url} alt="" loading="lazy" />
                              ) : (
                                initialOf(song.title)
                              )}
                            </span>
                            <span className="se-lib-song-body">
                              <span className="se-lib-title">{song.title || "Untitled song"}</span>
                              <span className="se-lib-meta">
                                {song.style?.slice(0, 44) || "No style"}
                              </span>
                              {tags.length > 0 ? (
                                <span className="se-lib-tags">
                                  {tags.map((tag) => (
                                    <span key={tag}>{tag}</span>
                                  ))}
                                </span>
                              ) : null}
                            </span>
                            <span className="se-lib-song-actions">
                              <button
                                type="button"
                                className="se-lib-icon"
                                aria-label={`${playingSongId === song.id ? "Pause" : "Play"} ${
                                  song.title || "song"
                                }`}
                                onClick={() => onTogglePlay(song)}
                              >
                                <Icon name={playingSongId === song.id ? "fa-pause" : "fa-play"} />
                              </button>
                              <button
                                type="button"
                                className={`se-lib-icon${isLiked(song) ? " on" : ""}`}
                                aria-label={`${isLiked(song) ? "Unlike" : "Like"} ${
                                  song.title || "song"
                                }`}
                                aria-pressed={isLiked(song)}
                                onClick={() => onToggleLike(song, !isLiked(song))}
                              >
                                <Icon name="fa-heart" />
                              </button>
                              <button
                                type="button"
                                className="se-pill"
                                onClick={() => onAddSong(song)}
                                disabled={!clip?.audio_url}
                              >
                                Add
                              </button>
                            </span>
                          </li>
                        );
                      })}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </>
        ) : (
          <>
            <div className="se-lib-tools" role="toolbar" aria-label="Upload actions">
              {uploadControl}
            </div>
            {uploadError ? (
              <p className="se-lib-empty" role="alert">
                {uploadError}
              </p>
            ) : null}
            {uploads === null ? (
              <p className="se-lib-empty">Loading uploads…</p>
            ) : visibleUploads.length === 0 ? (
              <p className="se-lib-empty">No uploads yet. Audio you import appears here.</p>
            ) : (
              <ul className="se-lib-list">
                {groupByDay(visibleUploads).map((group) => (
                  <li key={group.label} className="se-lib-day" aria-label={group.label}>
                    <button
                      type="button"
                      className="se-lib-day-head"
                      aria-expanded={!collapsedDays.includes(group.label)}
                      onClick={() =>
                        setCollapsedDays((previous) =>
                          previous.includes(group.label)
                            ? previous.filter((label) => label !== group.label)
                            : [...previous, group.label]
                        )
                      }
                    >
                      <span>{group.label}</span>
                      <span aria-hidden="true">
                        {collapsedDays.includes(group.label) ? "›" : "⌄"}
                      </span>
                    </button>
                    {collapsedDays.includes(group.label) ? null : (
                      <ul>
                        {group.items.map((upload) => (
                          <li key={upload.id} className="se-lib-row se-lib-upload">
                            <span className="se-lib-thumb se-lib-thumb-upload" aria-hidden="true">
                              <Icon name="fa-file-audio" />
                            </span>
                            <span className="se-lib-title">{upload.filename}</span>
                            <span className="se-lib-meta">
                              {formatUploadLength(upload.duration_seconds)}
                            </span>
                            <span className="se-lib-song-actions">
                              <button
                                type="button"
                                className="se-lib-icon"
                                aria-label={`${
                                  playingUploadId === upload.id ? "Pause" : "Play"
                                } ${upload.filename}`}
                                onClick={() => onToggleUploadPlay(upload)}
                                disabled={!upload.url}
                              >
                                <Icon
                                  name={playingUploadId === upload.id ? "fa-pause" : "fa-play"}
                                />
                              </button>
                              <button
                                type="button"
                                className="se-pill"
                                onClick={() => onAddUpload(upload)}
                                disabled={!upload.url}
                                aria-label={`Add ${upload.filename}`}
                              >
                                Add
                              </button>
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </aside>
    );
  }
);
