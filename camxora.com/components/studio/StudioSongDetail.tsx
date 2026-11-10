"use client";

import { useEffect, useState } from "react";

import { Icon } from "@/components/Icon";
import { Waveform } from "@/components/studio/Waveform";
import type { WebMusicGeneration } from "@/lib/library-api";
import {
  addStudioProjectComment,
  listStudioProjectComments,
  type StudioShareComment,
} from "@/lib/studio-api";

/**
 * Song detail rail (extra capture, §100): double-clicking a library row swaps the list
 * for the song's own panel, matching the reference's `Go back · <title>` header,
 * Remix/Like/Dislike/More row, big Play, and Info / Stems tabs.
 *
 * Honest limits: key and BPM are not in our corpus (D-016), Remix/More and comments have
 * no captured contract here (D-011), and the Stems tab cannot list a set before a stems
 * job exists (B-005) — each is shown disabled with its reason rather than faked.
 */

export type StudioSongDetailProps = {
  width: number;
  song: WebMusicGeneration;
  liked: boolean;
  disliked: boolean;
  playing: boolean;
  onBack: () => void;
  onClose: () => void;
  onTogglePlay: (song: WebMusicGeneration) => void;
  onToggleLike: (song: WebMusicGeneration, next: boolean) => void;
  onToggleDislike: (song: WebMusicGeneration, next: boolean) => void;
  /** Project the comments belong to (they are project notes, shown in this rail). */
  projectId?: string | null;
  commentAuthor?: string;
  /** Remix generation state for this song (D-018 superseded for Remix). */
  remixing?: boolean;
  onRemix?: (song: WebMusicGeneration) => void;
};

function primaryClipOf(song: WebMusicGeneration) {
  return (song.clips ?? []).find((clip) => clip.audio_url) ?? (song.clips ?? [])[0] ?? null;
}

function duration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds <= 0) return "—";
  const total = Math.round(seconds);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

function dateLabel(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function StudioSongDetail(props: StudioSongDetailProps) {
  const { width, song, liked, disliked, playing, onBack, onClose } = props;
  const { onTogglePlay, onToggleLike, onToggleDislike, projectId, commentAuthor, remixing, onRemix } =
    props;
  const [tab, setTab] = useState<"info" | "stems">("info");
  const [showStyles, setShowStyles] = useState(false);
  const [showLyrics, setShowLyrics] = useState(false);
  const [copied, setCopied] = useState<"" | "styles" | "lyrics">("");
  const [commentsOpen, setCommentsOpen] = useState(true);
  const [comments, setComments] = useState<StudioShareComment[] | null>(null);
  const [commentBody, setCommentBody] = useState("");
  const [commentBusy, setCommentBusy] = useState(false);
  const [commentError, setCommentError] = useState("");
  const clip = primaryClipOf(song);
  const title = song.title || "Untitled song";

  useEffect(() => {
    if (!projectId) return;
    let active = true;
    listStudioProjectComments(projectId)
      .then((result) => {
        if (active) setComments(result.items ?? []);
      })
      .catch(() => {
        if (active) setComments([]);
      });
    return () => {
      active = false;
    };
  }, [projectId]);

  async function submitComment() {
    const body = commentBody.trim();
    if (!body || !projectId || commentBusy) return;
    setCommentBusy(true);
    setCommentError("");
    try {
      const created = await addStudioProjectComment(projectId, {
        authorName: commentAuthor || "You",
        body,
      });
      setComments((current) => [created, ...(current ?? [])]);
      setCommentBody("");
    } catch (cause) {
      setCommentError(cause instanceof Error ? cause.message : "Could not post the comment.");
    } finally {
      setCommentBusy(false);
    }
  }

  async function copy(kind: "styles" | "lyrics", value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(kind);
      window.setTimeout(() => setCopied(""), 1500);
    } catch {
      setCopied("");
    }
  }

  return (
    <aside className="se-library se-song-detail" aria-label="Song details" style={{ width }}>
      <div className="se-library-head">
        <button type="button" className="se-song-back" onClick={onBack} aria-label="Back to library">
          <Icon name="fa-chevron-left" />
          <span>{title}</span>
        </button>
        <button type="button" className="se-icon" onClick={onClose} aria-label="Close library">
          <Icon name="fa-xmark" />
        </button>
      </div>

      <div className="se-clip-hero se-song-hero">
        <span
          className="se-clip-art"
          style={
            clip?.image_url
              ? { backgroundImage: `url(${clip.image_url})`, backgroundSize: "cover", backgroundPosition: "center" }
              : undefined
          }
          aria-hidden="true"
        />
        <div className="se-clip-hero-text">
          <p className="se-clip-title">{title}</p>
          <p className="se-clip-date">
            {[duration(clip?.duration_seconds), dateLabel(song.created_at)].filter(Boolean).join(" · ")}
          </p>
        </div>
      </div>

      <div className="se-song-actions">
        <button
          type="button"
          className="se-pill"
          disabled={!onRemix || remixing || !song.style?.trim()}
          title={
            song.style?.trim()
              ? "Generate a new variation from this song's style"
              : "This song has no style to remix from"
          }
          onClick={() => onRemix?.(song)}
        >
          {remixing ? "Remixing…" : "Remix"}
        </button>
        <span className="se-song-icons">
        <button
          type="button"
          className={`se-lib-icon${liked ? " on" : ""}`}
          aria-label={`${liked ? "Unlike" : "Like"} ${title}`}
          aria-pressed={liked}
          onClick={() => onToggleLike(song, !liked)}
        >
          <Icon name="fa-heart" />
        </button>
        <button
          type="button"
          className={`se-lib-icon${disliked ? " on" : ""}`}
          aria-label={`${disliked ? "Remove dislike for" : "Dislike"} ${title}`}
          aria-pressed={disliked}
          onClick={() => onToggleDislike(song, !disliked)}
        >
          <Icon name="fa-thumbs-down" />
        </button>
        <button
          type="button"
          className="se-lib-icon"
          aria-label="More song options"
          disabled
          title="The captured song menu is not wired yet"
        >
          <Icon name="fa-ellipsis" />
        </button>
        </span>
      </div>

      <div className="se-song-player">
        <button
          type="button"
          className="se-song-play"
          aria-label={`${playing ? "Pause" : "Play"} ${title}`}
          onClick={() => onTogglePlay(song)}
          disabled={!clip?.audio_url}
        >
          <Icon name={playing ? "fa-pause" : "fa-play"} />
        </button>
        <Waveform
          url={clip?.download_url ?? clip?.audio_url}
          width={240}
          height={40}
          className="se-song-wave"
          label="Song waveform"
        />
      </div>

      <div className="se-lib-tabs" role="tablist" aria-label="Song sections">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "info"}
          className={`se-lib-tab${tab === "info" ? " on" : ""}`}
          onClick={() => setTab("info")}
        >
          Info
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "stems"}
          className={`se-lib-tab${tab === "stems" ? " on" : ""}`}
          onClick={() => setTab("stems")}
        >
          Stems
        </button>
      </div>

      {tab === "info" ? (
        <div className="se-song-body">
          <section className="se-song-section" aria-label="Styles">
            <header>
              <span>Styles</span>
              <button
                type="button"
                className="se-lib-icon"
                aria-label="Copy styles to clipboard"
                onClick={() => void copy("styles", song.style || "")}
              >
                <Icon name="fa-copy" />
              </button>
            </header>
            <p className={showStyles ? "" : "se-song-clamp"}>{song.style || "No styles"}</p>
            {copied === "styles" ? <span className="se-song-copied">Copied</span> : null}
            {song.style && song.style.length > 80 ? (
              <button type="button" className="se-song-more" onClick={() => setShowStyles((v) => !v)}>
                {showStyles ? "Show less" : "Show more"}
              </button>
            ) : null}
          </section>

          <section className="se-song-section" aria-label="Lyrics">
            <header>
              <span>Lyrics</span>
              <button
                type="button"
                className="se-lib-icon"
                aria-label="Copy lyrics to clipboard"
                onClick={() => void copy("lyrics", song.lyrics || "")}
              >
                <Icon name="fa-copy" />
              </button>
            </header>
            <p className={`se-song-lyrics${showLyrics ? "" : " se-song-clamp"}`}>
              {song.lyrics || "Instrumental"}
            </p>
            {copied === "lyrics" ? <span className="se-song-copied">Copied</span> : null}
            {song.lyrics && song.lyrics.length > 120 ? (
              <button type="button" className="se-song-more" onClick={() => setShowLyrics((v) => !v)}>
                {showLyrics ? "Show less" : "Show more"}
              </button>
            ) : null}
          </section>

          <section className="se-song-section" aria-label="Comments and notes">
            <header>
              <button
                type="button"
                className="se-song-comments-toggle"
                aria-expanded={commentsOpen}
                onClick={() => setCommentsOpen((open) => !open)}
              >
                <Icon name={commentsOpen ? "fa-chevron-down" : "fa-chevron-right"} />
                <span>Comments and notes</span>
              </button>
            </header>
            {commentsOpen ? (
              <>
                {comments === null ? (
                  <p className="se-song-comment-note">Loading comments</p>
                ) : comments.length === 0 ? (
                  <p className="se-song-comment-note">No comments yet.</p>
                ) : (
                  <ul className="se-song-comment-list">
                    {comments.map((comment) => (
                      <li key={comment.id} className="se-song-comment-item">
                        <span>
                          <strong>{comment.author_name}</strong>{" "}
                          <small>
                            {comment.created_at
                              ? new Date(comment.created_at).toLocaleString()
                              : ""}
                          </small>
                        </span>
                        <p>{comment.body}</p>
                      </li>
                    ))}
                  </ul>
                )}
                {commentError ? (
                  <p className="se-song-comment-note" role="alert">
                    {commentError}
                  </p>
                ) : null}
                <div className="se-song-comment">
                  <input
                    type="text"
                    aria-label="Comment"
                    placeholder="Write a comment"
                    value={commentBody}
                    disabled={!projectId || commentBusy}
                    onChange={(event) => setCommentBody(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") void submitComment();
                    }}
                  />
                  <button
                    type="button"
                    className="se-song-comment-send"
                    aria-label="Send comment"
                    disabled={!commentBody.trim() || !projectId || commentBusy}
                    onClick={() => void submitComment()}
                  >
                    <Icon name="fa-arrow-up" />
                  </button>
                </div>
              </>
            ) : null}
          </section>
        </div>
      ) : (
        <div className="se-song-body">
          <p className="se-lib-empty">
            Stems cannot be listed before a finished separation exists for this song (B-005).
          </p>
        </div>
      )}

      {/* Captured sticky mini-player (EXTRA detail): the song stays playable while reading. */}
      <div className="se-song-mini" aria-label="Now playing">
        <span className="se-song-mini-art" aria-hidden="true">
          {clip?.image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={clip.image_url} alt="" loading="lazy" />
          ) : (
            (title.trim()[0] || "S").toUpperCase()
          )}
        </span>
        <span className="se-song-mini-text">
          <strong>{title}</strong>
          <small>
            {[song.model_label || song.model, duration(clip?.duration_seconds)]
              .filter(Boolean)
              .join(" · ")}
          </small>
        </span>
        <Waveform
          url={clip?.download_url ?? clip?.audio_url}
          width={96}
          height={24}
          className="se-song-mini-wave"
          label={`${title} mini waveform`}
        />
        <button
          type="button"
          className="se-song-mini-play"
          aria-label={`${playing ? "Pause" : "Play"} ${title}`}
          onClick={() => onTogglePlay(song)}
          disabled={!clip?.audio_url}
        >
          <Icon name={playing ? "fa-pause" : "fa-play"} />
        </button>
      </div>
    </aside>
  );
}
