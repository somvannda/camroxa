import type { StudioProjectThumb } from "@/lib/studio-api";

/**
 * S04: the mini-timeline on a project card.
 *
 * Bars are positioned from the project's own clip spans, scaled to the longest track, so
 * the card is a real preview of the arrangement rather than generic art. A project with
 * no clips falls back to the neutral placeholder.
 */
export function StudioProjectThumbView({ thumb }: { thumb?: StudioProjectThumb | null }) {
  const rows = thumb?.tracks ?? [];
  const end = thumb?.end ?? 0;
  const drawable = rows.some((row) => row.clips.length > 0) && end > 0;
  if (!drawable) {
    return (
      <span className="se-project-preview" aria-hidden="true">
        <span />
      </span>
    );
  }
  return (
    <span className="se-project-preview is-thumb" aria-label="Arrangement preview" role="img">
      {rows.map((row, index) => (
        <span key={index} className="se-thumb-row">
          {row.clips.map((clip, at) => (
            <span
              key={at}
              className="se-thumb-clip"
              style={{
                left: `${(clip.s / end) * 100}%`,
                width: `${Math.max(1.5, (clip.d / end) * 100)}%`,
                background: row.c,
              }}
            />
          ))}
        </span>
      ))}
    </span>
  );
}
