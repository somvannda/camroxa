"use client";

import Link from "next/link";
import { useState } from "react";
import { Icon } from "@/components/Icon";
import type { WebMusicClip, WebMusicGeneration } from "@/lib/library-api";
import type { WebMusicPlaylistSummary } from "@/lib/web-music-api";
import {
  clipDownloadUrl,
  clipIsReady,
  clipVersionLabel,
  formatDate,
  generationIsInstrumental,
  percent,
  statusClass,
  statusLabel,
  timeAgo,
  vocalLabel,
} from "@/lib/clip-utils";

export type TrackRailProps = {
  detail: WebMusicGeneration | null;
  clip: WebMusicClip | null;
  liked: boolean;
  playlists: WebMusicPlaylistSummary[];
  loading?: boolean;
  onClose?: () => void;
  onPlay?: () => void;
  onLike?: () => void;
  onUnlock?: () => void;
  onDelete?: () => void;
  onRename?: (title: string, variant?: string) => Promise<boolean>;
  onAddToPlaylist?: (playlist: WebMusicPlaylistSummary) => Promise<void>;
  onCreatePlaylist?: (name: string) => Promise<WebMusicPlaylistSummary | null>;
};

export function TrackRail({
  detail,
  clip,
  liked,
  playlists,
  loading = false,
  onClose,
  onPlay,
  onLike,
  onUnlock,
  onDelete,
  onRename,
  onAddToPlaylist,
  onCreatePlaylist,
}: TrackRailProps) {
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [copied, setCopied] = useState<"style" | "lyrics" | null>(null);
  const [styleExpanded, setStyleExpanded] = useState(false);
  const [settingsExpanded, setSettingsExpanded] = useState(false);
  const [lyricsExpanded, setLyricsExpanded] = useState(false);
  const [playlistOpen, setPlaylistOpen] = useState(false);
  const [playlistBusy, setPlaylistBusy] = useState(false);
  const [newPlaylistName, setNewPlaylistName] = useState("");
  const [renaming, setRenaming] = useState(false);

  const ready = detail && clip ? clipIsReady(detail, clip) : false;
  const instrumental = detail ? generationIsInstrumental(detail) : false;
  const cover = clip?.image_url || "/hero.png";
  const title = clip?.title || detail?.title || "Untitled";

  async function copyText(text: string, kind: "style" | "lyrics") {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(kind);
      window.setTimeout(() => setCopied(null), 1600);
    } catch {
      /* clipboard can be blocked; the text stays selectable */
    }
  }

  async function commitTitle() {
    const next = titleDraft.trim();
    if (!detail || !onRename || !next || renaming) return;
    setRenaming(true);
    try {
      const ok = await onRename(next, clip?.variant);
      if (ok) setEditingTitle(false);
    } finally {
      setRenaming(false);
    }
  }

  async function addToPlaylist(playlist: WebMusicPlaylistSummary) {
    if (!onAddToPlaylist || playlistBusy) return;
    setPlaylistBusy(true);
    try {
      await onAddToPlaylist(playlist);
      setPlaylistOpen(false);
    } finally {
      setPlaylistBusy(false);
    }
  }

  async function createPlaylist() {
    const name = newPlaylistName.trim();
    if (!onCreatePlaylist || !name || playlistBusy) return;
    setPlaylistBusy(true);
    try {
      const created = await onCreatePlaylist(name);
      if (created) setNewPlaylistName("");
    } finally {
      setPlaylistBusy(false);
    }
  }

  return (
    <aside className="s-detail-rail" aria-label={detail ? title : "Track details"}>
      <div className="s-rail-head">
        {onClose ? (
          <button
            type="button"
            className="s-btn s-btn-icon sm"
            aria-label="Close details"
            onClick={onClose}
          >
            <Icon name="fa-xmark" />
          </button>
        ) : (
          <span className="s-rail-kicker">Now selected</span>
        )}
      </div>

      <div className="s-rail-body">
        {loading && !detail ? (
          <div className="s-empty" style={{ padding: 16 }}>
            <span className="ico">
              <Icon name="fa-spinner" />
            </span>
            <b>Loading track</b>
            <p>Fetching lyrics, style, and settings.</p>
          </div>
        ) : !detail ? (
          <div className="s-empty" style={{ padding: 24 }}>
            <span className="ico">
              <Icon name="fa-music" />
            </span>
            <b>No clip selected</b>
            <p>Pick a clip from the list to see its settings, style, and lyrics here.</p>
          </div>
        ) : (
          <>
            <div className="s-rail-hero">
              <img src={cover} alt="" />
              <div className="s-rail-title">
                {editingTitle ? (
                  <div className="s-rail-rename">
                    <input
                      className="s-input"
                      autoFocus
                      value={titleDraft}
                      onChange={(event) => setTitleDraft(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") void commitTitle();
                        if (event.key === "Escape") setEditingTitle(false);
                      }}
                      maxLength={200}
                      aria-label="Track title"
                    />
                    <button
                      type="button"
                      className="s-btn s-btn-icon sm"
                      onClick={() => void commitTitle()}
                      disabled={renaming}
                      aria-label="Save title"
                    >
                      <Icon name="fa-check" />
                    </button>
                    <button
                      type="button"
                      className="s-btn s-btn-icon sm"
                      onClick={() => setEditingTitle(false)}
                      aria-label="Cancel title edit"
                    >
                      <Icon name="fa-xmark" />
                    </button>
                  </div>
                ) : (
                  <h4>
                    <span>{title}</span>
                    <button
                      type="button"
                      className="s-btn s-btn-icon sm"
                      onClick={() => {
                        setTitleDraft(title);
                        setEditingTitle(true);
                      }}
                      aria-label="Rename track"
                    >
                      <Icon name="fa-pen" />
                    </button>
                  </h4>
                )}
                <div className="s-rail-sub">
                  <span className={`s-status ${ready ? "ok" : statusClass(detail.status)}`}>
                    {ready ? "Ready" : statusLabel(detail.status)}
                  </span>
                  <span>{clipVersionLabel(clip?.variant)}</span>
                  <span className="s-rail-dot" aria-hidden="true">·</span>
                  <span>{detail.model_label || detail.model || "V6"}</span>
                  <span className="s-rail-dot" aria-hidden="true">·</span>
                  <span title={detail.created_at ? formatDate(detail.created_at) : undefined}>
                    {timeAgo(detail.created_at) || formatDate(detail.created_at)}
                  </span>
                  {instrumental ? <span className="s-tag">Instrumental</span> : null}
                  {detail.is_preview ? <span className="s-status live">Preview</span> : null}
                </div>
              </div>
            </div>

            <div className="s-rail-actions">
              <button
                type="button"
                className="s-btn s-btn-primary s-btn-block"
                onClick={() => onPlay?.()}
                disabled={!ready}
              >
                <Icon name="fa-play" /> Play
              </button>
            </div>

            <div className="s-rail-action-grid">
              <button
                type="button"
                className="s-btn s-btn-secondary"
                onClick={() => setPlaylistOpen((value) => !value)}
                disabled={!ready || !clip?.ready || playlistBusy || !onAddToPlaylist}
                aria-expanded={playlistOpen}
              >
                <Icon name="fa-list" /> Playlist
              </button>
              <button
                type="button"
                className={`s-btn s-btn-secondary${liked ? " on" : ""}`}
                onClick={() => onLike?.()}
                aria-pressed={liked}
                disabled={!onLike}
              >
                <Icon name="fa-heart" /> {liked ? "Liked" : "Like"}
              </button>
              {ready && clip && !instrumental ? (
                <a className="s-btn s-btn-secondary" href={clipDownloadUrl(detail.id, clip.variant || "ok", "lrc")}>
                  LRC
                </a>
              ) : null}
              {ready && clip && !instrumental ? (
                <a className="s-btn s-btn-secondary" href={clipDownloadUrl(detail.id, clip.variant || "ok", "srt")}>
                  SRT
                </a>
              ) : null}
              {ready && clip ? (
                <a className="s-btn s-btn-secondary" href={clip.download_url || clipDownloadUrl(detail.id, clip.variant || "ok", "mp3")}>
                  MP3
                </a>
              ) : null}
              {ready && clip ? (
                <a className="s-btn s-btn-secondary" href={clipDownloadUrl(detail.id, clip.variant || "ok", "wav")}>
                  WAV
                </a>
              ) : null}
              {detail.unlockable ? (
                <button
                  type="button"
                  className="s-btn s-btn-secondary"
                  onClick={() => onUnlock?.()}
                  disabled={loading}
                >
                  <Icon name="fa-lock-open" /> Unlock
                </button>
              ) : null}
            </div>

            {playlistOpen ? (
              <div className="s-rail-card s-rail-playlists">
                <div className="s-rail-card-head">
                  <span>Add to playlist</span>
                  <button
                    type="button"
                    className="s-btn s-btn-icon sm"
                    onClick={() => setPlaylistOpen(false)}
                    aria-label="Close playlist menu"
                  >
                    <Icon name="fa-xmark" />
                  </button>
                </div>
                {playlists.length ? (
                  playlists.map((playlist) => (
                    <button
                      key={playlist.id}
                      type="button"
                      className="s-rail-playlist"
                      onClick={() => void addToPlaylist(playlist)}
                      disabled={playlistBusy}
                    >
                      <Icon name="fa-music" />
                      <span>{playlist.name}</span>
                      <small>{playlist.song_count ?? 0}</small>
                    </button>
                  ))
                ) : (
                  <p className="s-note" style={{ padding: "4px 2px" }}>
                    No playlists yet. Create one below.
                  </p>
                )}
                <div className="s-rail-playlist-new">
                  <input
                    className="s-input"
                    value={newPlaylistName}
                    onChange={(event) => setNewPlaylistName(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") void createPlaylist();
                    }}
                    placeholder="New playlist"
                    aria-label="New playlist name"
                    maxLength={120}
                  />
                  <button
                    type="button"
                    className="s-btn s-btn-icon sm"
                    onClick={() => void createPlaylist()}
                    disabled={playlistBusy || !newPlaylistName.trim()}
                    aria-label="Create playlist"
                  >
                    <Icon name="fa-plus" />
                  </button>
                </div>
              </div>
            ) : null}

            <section className="s-rail-card">
              <h5>Settings</h5>
              <dl className="s-rail-kv">
                <dt>Model</dt>
                <dd>{detail.model_label || detail.model || "V6"}</dd>
                <dt>Type</dt>
                <dd>{instrumental ? "Instrumental" : "With Vocals"}</dd>
                {settingsExpanded ? (
                  <>
                    <dt>Vocal Gender</dt>
                    <dd>{instrumental ? "Not set" : vocalLabel(detail.vocal_gender)}</dd>
                    <dt>Style Influence</dt>
                    <dd>{percent(detail.style_weight)}</dd>
                    <dt>Weirdness</dt>
                    <dd>{percent(detail.weirdness_constraint)}</dd>
                    <dt>Audio Weight</dt>
                    <dd>{percent(detail.audio_weight)}</dd>
                  </>
                ) : null}
                <dt>Status</dt>
                <dd>{ready ? "Ready" : statusLabel(detail.status)}</dd>
              </dl>
              <button
                type="button"
                className="s-rail-more"
                aria-expanded={settingsExpanded}
                onClick={() => setSettingsExpanded((value) => !value)}
              >
                {settingsExpanded ? "Show less" : "Show more"}
                <Icon name={settingsExpanded ? "fa-chevron-up" : "fa-chevron-down"} />
              </button>
            </section>

            {detail.negative_tags ? (
              <section className="s-rail-card">
                <h5>Exclude styles</h5>
                <p className="s-rail-text">{detail.negative_tags}</p>
              </section>
            ) : null}

            <section className="s-rail-card">
              <div className="s-rail-card-head">
                <h5>Style</h5>
                <button
                  type="button"
                  className="s-btn s-btn-icon sm"
                  onClick={() => void copyText(detail.style || "", "style")}
                  aria-label="Copy style"
                >
                  <Icon name={copied === "style" ? "fa-check" : "fa-copy"} />
                </button>
              </div>
              <p className={`s-rail-text${styleExpanded ? "" : " clamp-4"}`}>
                {detail.style || "—"}
              </p>
              {(detail.style || "").length > 90 ? (
                <button
                  type="button"
                  className="s-rail-more"
                  aria-expanded={styleExpanded}
                  onClick={() => setStyleExpanded((value) => !value)}
                >
                  {styleExpanded ? "Show less" : "Show more"}
                  <Icon name={styleExpanded ? "fa-chevron-up" : "fa-chevron-down"} />
                </button>
              ) : null}
            </section>

            <section className="s-rail-card">
              <div className="s-rail-card-head">
                <h5>Lyrics</h5>
                <button
                  type="button"
                  className="s-btn s-btn-icon sm"
                  onClick={() => void copyText(detail.lyrics || "", "lyrics")}
                  aria-label="Copy lyrics"
                >
                  <Icon name={copied === "lyrics" ? "fa-check" : "fa-copy"} />
                </button>
              </div>
              <p className={`s-rail-text${lyricsExpanded ? "" : " clamp-4"}`}>
                {instrumental ? "Instrumental — no lyrics" : detail.lyrics || "No lyrics saved."}
              </p>
              {!instrumental && (detail.lyrics || "").length > 160 ? (
                <button
                  type="button"
                  className="s-rail-more"
                  aria-expanded={lyricsExpanded}
                  onClick={() => setLyricsExpanded((value) => !value)}
                >
                  {lyricsExpanded ? "Show less" : "Show more"}
                  <Icon name={lyricsExpanded ? "fa-chevron-up" : "fa-chevron-down"} />
                </button>
              ) : null}
            </section>
          </>
        )}
      </div>

      {detail && onDelete ? (
        <div className="s-rail-foot">
          <Link className="s-btn s-btn-ghost s-btn-sm" href="/studio/editor">
            <Icon name="fa-wand-magic-sparkles" /> Remix / Edit
          </Link>
          <span style={{ flex: 1 }} />
          <button
            type="button"
            className="s-btn s-btn-ghost s-btn-sm s-danger-text"
            onClick={() => onDelete()}
          >
            <Icon name="fa-trash" /> Delete
          </button>
        </div>
      ) : null}
    </aside>
  );
}
