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
 * Clip info panel (spec §70): the right rail swaps from the library to an inspector for
 * the selected clip.
 *
 * Shows what the document knows (timing, fade, trim offset, track), the source
 * generation (model, style, lyrics), a decoded waveform, the Stems request, and the
 * captured S55 "Comments and notes" section: anonymous plain-text notes on this clip
 * with a `Write a comment` pill — the reference deliberately shows no author or time.
 *
 * Anatomy follows S27: header, artwork hero, Remix affordance, waveform player,
 * Info/Stems tabs, then quiet section cards.
 */

export type StudioClipInfoProps = {
  width: number;
  clip: {
    id: string;
    title?: string;
    start?: number;
    duration?: number;
    offset?: number;
    fadeIn?: number;
    fadeOut?: number;
    color?: string;
    audioUrl?: string | null;
    songId?: string;
  };
  trackName?: string;
  /** Enables the clip's comments section; omitted in contexts without a project. */
  projectId?: string;
  source: WebMusicGeneration | null;
  stems: { status: string; message?: string } | null;
  onRequestStems: () => void;
  /** Generate a variation from the source song's style (S37 Remix). */
  onRemix?: () => void;
  remixing?: boolean;
  onClose: () => void;
};

function mmss(seconds: number | undefined): string {
  const safe = Math.max(0, Number(seconds) || 0);
  const m = Math.floor(safe / 60);
  const rest = safe % 60;
  return `${m}:${rest.toFixed(2).padStart(5, "0")}`;
}

function sourceDate(source: WebMusicGeneration | null): string | null {
  if (!source?.created_at) return null;
  const value = new Date(source.created_at);
  if (Number.isNaN(value.getTime())) return null;
  return value.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function StudioClipInfo(props: StudioClipInfoProps) {
  const {
    width,
    clip,
    trackName,
    projectId,
    source,
    stems,
    onRequestStems,
    onRemix,
    remixing = false,
    onClose,
  } = props;
  // Ready assets reject the raw stream URL (encrypted-player guard); the download
  // endpoint returns the same audio as a plain file and is what the waveform can decode.
  const waveformUrl =
    source?.clips?.find((candidate) => candidate.audio_url === clip.audioUrl)?.download_url ??
    clip.audioUrl;
  const [tab, setTab] = useState<"info" | "stems">("info");
  const date = sourceDate(source);
  const [comments, setComments] = useState<StudioShareComment[] | null>(null);
  const [commentDraft, setCommentDraft] = useState("");
  const [commentBusy, setCommentBusy] = useState(false);
  const [commentError, setCommentError] = useState("");
  const [commentsOpen, setCommentsOpen] = useState(true);

  useEffect(() => {
    if (!projectId) return;
    let active = true;
    setComments(null);
    listStudioProjectComments(projectId, 100, clip.id)
      .then((payload) => {
        if (active) setComments(payload.items);
      })
      .catch(() => {
        if (active) setComments([]);
      });
    return () => {
      active = false;
    };
  }, [projectId, clip.id]);

  async function submitComment() {
    const text = commentDraft.trim();
    if (!projectId || !text || commentBusy) return;
    setCommentBusy(true);
    setCommentError("");
    try {
      const created = await addStudioProjectComment(projectId, {
        authorName: "You",
        body: text,
        clipId: clip.id,
      });
      setComments((current) => [created, ...(current ?? [])]);
      setCommentDraft("");
    } catch (cause) {
      setCommentError(cause instanceof Error ? cause.message : "Could not save the comment");
    } finally {
      setCommentBusy(false);
    }
  }

  return (
    <aside className="se-inspector" aria-label="Clip info" style={{ width }}>
      <div className="se-inspector-head">
        <button type="button" className="se-icon" aria-label="Back to arrangement" onClick={onClose}>
          <Icon name="fa-chevron-left" />
        </button>
        <strong>{clip.title || "Clip"}</strong>
      </div>

      <div className="se-inspector-body">
        <div className="se-clip-hero">
          <span
            className="se-clip-art"
            style={{ background: clip.color || "hsl(var(--accent))" }}
            aria-hidden="true"
          />
          <div className="se-clip-hero-text">
            <p className="se-clip-title">{source?.title || clip.title || "Clip"}</p>
            {date ? <p className="se-clip-date">{date}</p> : null}
          </div>
        </div>

        <button
          type="button"
          className="se-clip-remix"
          disabled={!onRemix || remixing}
          title={
            onRemix
              ? "Generate a variation from this song's style"
              : "This clip has no source song"
          }
          onClick={() => onRemix?.()}
        >
          <Icon name="fa-rotate" /> {remixing ? "Remixing..." : "Remix"}
        </button>

        <div className="se-clip-player">
          <Waveform
            url={waveformUrl}
            width={width - 32}
            height={44}
            className="se-inspector-wave"
            label="Clip waveform"
            color="#4ade80"
          />
        </div>

        <div className="se-lib-tabs" role="tablist" aria-label="Clip sections">
          {(["info", "stems"] as const).map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={tab === value}
              className={`se-lib-tab${tab === value ? " on" : ""}`}
              onClick={() => setTab(value)}
            >
              {value === "info" ? "Info" : "Stems"}
            </button>
          ))}
        </div>

        {tab === "info" ? (
          <div className="se-clip-cards">
            <section className="se-clip-card" aria-label="Source">
              <p className="se-clip-card-label">Source</p>
              {source ? (
                <>
                  <p className="se-clip-card-value">{source.title || "Untitled"}</p>
                  <p className="se-clip-card-meta">
                    {source.model_label || source.model || "model"}
                  </p>
                </>
              ) : (
                <p className="se-clip-card-meta">
                  This clip has no source generation. Uploads and recorded takes keep their own
                  details.
                </p>
              )}
            </section>

            <section className="se-clip-card" aria-label="Styles">
              <p className="se-clip-card-label">Styles</p>
              <p className="se-clip-card-meta">{source?.style?.trim() || "No styles"}</p>
            </section>

            <section className="se-clip-card" aria-label="Lyrics">
              <p className="se-clip-card-label">Lyrics</p>
              <pre className="se-clip-lyrics">{source?.lyrics?.trim() || "No lyrics"}</pre>
            </section>

            <section className="se-clip-card" aria-label="Details">
              <p className="se-clip-card-label">Details</p>
              <dl className="se-clip-facts">
                <div>
                  <dt>Track</dt>
                  <dd>{trackName || "—"}</dd>
                </div>
                <div>
                  <dt>Start</dt>
                  <dd>{mmss(clip.start)}</dd>
                </div>
                <div>
                  <dt>Length</dt>
                  <dd>{mmss(clip.duration)}</dd>
                </div>
                <div>
                  <dt>Fade in</dt>
                  <dd>{clip.fadeIn ? mmss(clip.fadeIn) : "None"}</dd>
                </div>
                <div>
                  <dt>Fade out</dt>
                  <dd>{clip.fadeOut ? mmss(clip.fadeOut) : "None"}</dd>
                </div>
                <div>
                  <dt>Trim offset</dt>
                  <dd>{clip.offset ? mmss(clip.offset) : "None"}</dd>
                </div>
              </dl>
            </section>

            <section className="se-clip-card se-comments" aria-label="Comments and notes">
              <button
                type="button"
                className="se-comments-head"
                aria-expanded={commentsOpen}
                onClick={() => setCommentsOpen((open) => !open)}
              >
                <Icon name={commentsOpen ? "fa-chevron-down" : "fa-chevron-right"} />
                <span>Comments and notes</span>
              </button>
              {commentsOpen ? (
                <>
                  {comments === null ? (
                    <p className="se-clip-card-meta">Loading comments…</p>
                  ) : null}
                  {comments && comments.length === 0 ? (
                    <p className="se-clip-card-meta">No comments yet.</p>
                  ) : null}
                  {[...(comments ?? [])].reverse().map((comment) => (
                    <p key={comment.id} className="se-comment">
                      {comment.body}
                    </p>
                  ))}
                  {projectId ? (
                    <div className="se-comment-input">
                      <input
                        value={commentDraft}
                        placeholder="Write a comment"
                        aria-label="Write a comment"
                        disabled={commentBusy}
                        onChange={(event) => setCommentDraft(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            void submitComment();
                          }
                        }}
                      />
                      <button
                        type="button"
                        className="se-icon"
                        aria-label="Post comment"
                        disabled={commentBusy || !commentDraft.trim()}
                        onClick={() => void submitComment()}
                      >
                        <Icon name="fa-arrow-up" />
                      </button>
                    </div>
                  ) : null}
                  {commentError ? (
                    <p className="se-clip-card-meta" role="alert">
                      {commentError}
                    </p>
                  ) : null}
                </>
              ) : null}
            </section>
          </div>
        ) : (
          <div className="se-inspector-stems">
            <p className="se-inspector-meta">
              Separating stems renders them on this project's server account; the request is
              charged like any other Studio operation.
            </p>
            <button
              type="button"
              className="se-pill on"
              onClick={onRequestStems}
              disabled={!source}
              title={source ? undefined : "Get stems needs a clip from a generation"}
            >
              Get stems
            </button>
            {stems ? (
              <p className="se-inspector-meta">
                {stems.status}
                {stems.message ? ` — ${stems.message}` : ""}
              </p>
            ) : (
              <p className="se-inspector-meta">No stems requested for this clip yet.</p>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
