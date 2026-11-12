"use client";

import type { WebMusicGeneration } from "@/lib/library-api";

/**
 * Provenance strip for the selected clip (spec §70): which song it came from, when,
 * in what style, plus the stem-separation action (W4.2).
 *
 * Extracted from the shell (roadmap G15). It renders nothing without a source, so the
 * shell can drop it in unconditionally.
 */

export type ClipSourceStripProps = {
  source: WebMusicGeneration | null;
  stems: { status: string; message?: string } | null;
  onRequestStems: () => void;
};

export function ClipSourceStrip({ source, stems, onRequestStems }: ClipSourceStripProps) {
  if (!source) return null;

  const created = source.created_at
    ? new Date(source.created_at).toLocaleDateString()
    : "unknown date";

  return (
    <div className="se-clip-source" aria-label="Clip source">
      <strong>{source.title || "Untitled song"}</strong>
      <span>
        {source.model_label || source.model || "model"} · {created}
        {source.style ? ` · ${source.style.slice(0, 60)}` : ""}
      </span>
      <div className="se-clip-source-actions">
        <button type="button" className="se-pill" onClick={onRequestStems}>
          Get stems
        </button>
        {stems ? (
          <em className={`se-stem-status ${stems.status === "error" ? "off" : ""}`}>
            {stems.status === "added" ? "stems added as tracks" : stems.message ?? stems.status}
          </em>
        ) : null}
      </div>
    </div>
  );
}
