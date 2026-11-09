"use client";

import { useState } from "react";

import { Icon } from "@/components/Icon";
import { Waveform } from "@/components/studio/Waveform";
import type { WebMusicGeneration } from "@/lib/library-api";

/**
 * Clip info panel (spec §70): the right rail swaps from the library to an inspector for
 * the selected clip.
 *
 * Read-only by design: it shows what the document knows (timing, fade, trim offset, track)
 * plus the source generation (model, style, lyrics) and a real decoded waveform. The
 * Stems tab exposes the same request the provenance strip does; comments and the Magic
 * Bar chip have no captured contract here, so they are absent rather than mocked.
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
    color?: string;
    audioUrl?: string | null;
    songId?: string;
  };
  trackName?: string;
  source: WebMusicGeneration | null;
  stems: { status: string; message?: string } | null;
  onRequestStems: () => void;
  onClose: () => void;
};

function mmss(seconds: number | undefined): string {
  const safe = Math.max(0, Number(seconds) || 0);
  const m = Math.floor(safe / 60);
  const rest = safe % 60;
  return `${m}:${rest.toFixed(2).padStart(5, "0")}`;
}

export function StudioClipInfo(props: StudioClipInfoProps) {
  const { width, clip, trackName, source, stems, onRequestStems, onClose } = props;
  // Ready assets reject the raw stream URL (encrypted-player guard); the download
  // endpoint returns the same audio as a plain file and is what the waveform can decode.
  const waveformUrl =
    source?.clips?.find((candidate) => candidate.audio_url === clip.audioUrl)?.download_url ??
    clip.audioUrl;
  const [tab, setTab] = useState<"info" | "stems">("info");

  return (
    <aside className="se-inspector" aria-label="Clip info" style={{ width }}>
      <div className="se-inspector-head">
        <button type="button" className="se-icon" aria-label="Back to arrangement" onClick={onClose}>
          <Icon name="fa-chevron-left" />
        </button>
        <strong>{clip.title || "Clip"}</strong>
        <span className="se-inspector-dot" style={{ background: clip.color || "hsl(var(--accent))" }} />
      </div>

      <div className="se-inspector-body">
        <dl className="se-inspector-facts">
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
            <dt>Trim offset</dt>
            <dd>{clip.offset ? mmss(clip.offset) : "None"}</dd>
          </div>
        </dl>

        <Waveform
          url={waveformUrl}
          width={320}
          height={56}
          className="se-inspector-wave"
          label="Clip waveform"
          color="#4ade80"
        />

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
          source ? (
            <div className="se-inspector-source">
              <p className="se-inspector-label">Source generation</p>
              <p className="se-inspector-title">{source.title || "Untitled"}</p>
              <p className="se-inspector-meta">
                {source.model_label || source.model || "model"} ·{" "}
                {source.created_at ? new Date(source.created_at).toLocaleDateString() : "unknown date"}
              </p>
              <p className="se-inspector-label">Style</p>
              <p className="se-inspector-meta">{source.style || "No style recorded"}</p>
              <p className="se-inspector-label">Lyrics</p>
              <pre className="se-inspector-lyrics">{source.lyrics?.trim() || "No lyrics"}</pre>
            </div>
          ) : (
            <p className="se-lib-empty">
              This clip has no source generation. Library uploads and recorded takes will show
              their own details here.
            </p>
          )
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
