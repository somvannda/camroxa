"use client";

import type { PointerEvent as ReactPointerEvent, RefObject } from "react";

import { dragToStart } from "@/lib/studio-snap";
import type { StudioTrack } from "@/lib/studio-tracks";

/**
 * Timeline: the two rulers, the lane grid with clips, and every overlay that lives on
 * the canvas (playhead, loop band + grip, marquee, snap line, empty state).
 *
 * Extracted from the shell (roadmap G15). It is deliberately presentational: the shell
 * owns the drag/marquee sessions and the project document, and passes both down as
 * props plus callbacks.
 */

export type TimelineClip = {
  id: string;
  title?: string;
  start?: number;
  duration?: number;
  audioUrl?: string | null;
  songId?: string;
};

export type TimelineDrag = {
  ids: string[];
  origins: Record<string, number>;
  deltaPx: number;
};

export type TimelineMarquee = { x1: number; y1: number; x2: number; y2: number };

export type StudioTimelineProps = {
  tracks: StudioTrack[];
  clips: TimelineClip[];
  barWidth: number;
  barCount: number;
  secondsPerBar: number;
  duration: number;
  playhead: number;
  clock: (seconds: number) => string;
  rowStep: number;

  selectedClip: string | null;
  selectedIds: string[];
  drag: TimelineDrag | null;
  marquee: TimelineMarquee | null;
  loop: boolean;
  loopStart: number;
  loopEnd: number;
  viewWidth: number;
  viewLeft: number;

  /** Receives the scroll container so the shell can measure the visible window. */
  timelineRef?: RefObject<HTMLDivElement | null>;
  onScroll: (left: number, width: number) => void;
  onLanePointerDown: (event: ReactPointerEvent<HTMLDivElement>) => void;
  onClipPointerDown: (event: ReactPointerEvent<HTMLButtonElement>, clip: TimelineClip, trackId: string) => void;
  onLoopHandleDown: (event: ReactPointerEvent<HTMLButtonElement>) => void;
};

export function StudioTimeline(props: StudioTimelineProps) {
  const {
    tracks,
    clips,
    barWidth,
    barCount,
    secondsPerBar,
    duration,
    playhead,
    clock,
    rowStep,
    selectedClip,
    selectedIds,
    drag,
    marquee,
    loop,
    loopStart,
    loopEnd,
    viewWidth,
    viewLeft,
    timelineRef,
    onScroll,
    onLanePointerDown,
    onClipPointerDown,
    onLoopHandleDown,
  } = props;

  return (
    <div
      className="se-timeline"
      ref={timelineRef}
      onScroll={(event) => {
        const el = event.currentTarget;
        onScroll(el.scrollLeft, el.clientWidth);
      }}
    >
      <div className="se-ruler-bars" aria-hidden="true">
        <div className="se-ruler-inner" style={{ width: barCount * barWidth }}>
          {Array.from({ length: barCount }).map((_, bar) => (
            <span key={bar} className="se-bar-tick" style={{ left: bar * barWidth }}>
              {bar + 1}
            </span>
          ))}
        </div>
      </div>

      <div className="se-lanes" onPointerDown={onLanePointerDown}>
        <div className="se-lanes-inner" style={{ width: barCount * barWidth }}>
          {tracks.map((track) => (
            <div key={track.id} className="se-lane" style={{ height: rowStep }}>
              {clips
                .filter((clip) => track.clipIds.includes(clip.id))
                .filter((clip) => {
                  // Cull clips outside the visible window plus a screen of slack (G19).
                  if (viewWidth === 0) return true;
                  const left = ((clip.start ?? 0) / secondsPerBar) * barWidth;
                  const width = Math.max(20, ((clip.duration ?? 4) / secondsPerBar) * barWidth);
                  return (
                    left + width >= viewLeft - viewWidth && left <= viewLeft + viewWidth + viewWidth
                  );
                })
                .map((clip) => {
                  const isDragging = drag?.ids.includes(clip.id) ?? false;
                  const isSelected = selectedClip === clip.id || selectedIds.includes(clip.id);
                  const dragOrigin = drag ? drag.origins[clip.id] : undefined;
                  const left =
                    isDragging && drag && dragOrigin !== undefined
                      ? (dragToStart(dragOrigin, drag.deltaPx, barWidth, secondsPerBar, 4) /
                          secondsPerBar) *
                        barWidth
                      : ((clip.start ?? 0) / secondsPerBar) * barWidth;
                  const width = Math.max(20, ((clip.duration ?? 4) / secondsPerBar) * barWidth);
                  return (
                    <button
                      type="button"
                      key={clip.id}
                      className={`se-clip${isSelected ? " selected" : ""}${
                        isDragging ? " dragging" : ""
                      }`}
                      style={{ left, width, background: track.color }}
                      onPointerDown={(event) => onClipPointerDown(event, clip, track.id)}
                      aria-pressed={isSelected}
                    >
                      <span className="se-clip-head">{clip.title || "Clip"}</span>
                      <span className="se-clip-body" aria-hidden="true" />
                    </button>
                  );
                })}
            </div>
          ))}

          <div
            className="se-playhead"
            style={{ left: (playhead / secondsPerBar) * barWidth }}
            aria-hidden="true"
          />

          {loop && loopEnd > loopStart ? (
            <>
              <div
                className="se-loop-band"
                aria-hidden="true"
                style={{
                  left: (loopStart / secondsPerBar) * barWidth,
                  width: ((loopEnd - loopStart) / secondsPerBar) * barWidth,
                }}
              />
              <button
                type="button"
                className="se-loop-handle"
                aria-label="Loop end"
                style={{ left: (loopEnd / secondsPerBar) * barWidth }}
                onPointerDown={onLoopHandleDown}
              />
            </>
          ) : null}

          {marquee ? (
            <div
              className="se-marquee"
              aria-hidden="true"
              style={{
                left: Math.min(marquee.x1, marquee.x2),
                top: Math.min(marquee.y1, marquee.y2),
                width: Math.abs(marquee.x2 - marquee.x1),
                height: Math.abs(marquee.y2 - marquee.y1),
              }}
            />
          ) : null}

          {drag ? (
            <div
              className="se-snap-line"
              aria-hidden="true"
              style={{
                left:
                  (dragToStart(
                    drag.origins[drag.ids[0]] ?? 0,
                    drag.deltaPx,
                    barWidth,
                    secondsPerBar,
                    4
                  ) /
                    secondsPerBar) *
                  barWidth,
              }}
            />
          ) : null}
        </div>

        {!tracks.length ? (
          <div className="se-empty">
            <strong>Your session is empty</strong>
            <span>Add a track to start arranging.</span>
          </div>
        ) : null}
      </div>

      <div className="se-ruler-time" aria-hidden="true">
        <div className="se-ruler-inner" style={{ width: barCount * barWidth }}>
          {Array.from({ length: Math.ceil(duration / 30) }).map((_, index) => (
            <span
              key={index}
              className="se-time-tick"
              style={{ left: ((index * 30) / secondsPerBar) * barWidth }}
            >
              {clock(index * 30).slice(0, 5)}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
