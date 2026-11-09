"use client";

import type { DragEvent as ReactDragEvent, PointerEvent as ReactPointerEvent, RefObject } from "react";

import { Waveform } from "@/components/studio/Waveform";
import { MIDI_MAX_PITCH, MIDI_MIN_PITCH, type MidiNote } from "@/lib/studio-midi";
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
  offset?: number;
  fadeIn?: number;
  /** Per-clip colour override (clip menu ▸ Clip Color); falls back to the track colour. */
  color?: string;
  audioUrl?: string | null;
  songId?: string;
  midi?: { notes?: MidiNote[] };
};

export type TimelineDrag = {
  ids: string[];
  origins: Record<string, number>;
  deltaPx: number;
};

export type TimelineMarquee = { x1: number; y1: number; x2: number; y2: number };

/**
 * Clip label colour for a clip fill. Pastel track colours (the editor's default
 * palette) need dark text to stay readable; the saturated reference colours keep
 * white. Keeps the captured look without failing contrast (axe color-contrast).
 */
/** Bottom-ruler label step: the smallest captured interval that keeps labels ~150 px apart. */
function timeTickStep(barWidth: number, secondsPerBar: number): number {
  const pxPerSecond = barWidth / Math.max(0.001, secondsPerBar);
  const steps = [5, 10, 15, 30, 60, 120, 300];
  return steps.find((step) => step * pxPerSecond >= 150) ?? 600;
}

function labelOn(fill: string): string {
  const value = fill.replace("#", "");
  if (value.length !== 6) return "#ffffff";
  const channel = (index: number) => parseInt(value.slice(index, index + 2), 16) / 255;
  const luminance = 0.2126 * channel(0) + 0.7152 * channel(2) + 0.0722 * channel(4);
  return luminance > 0.55 ? "#111111" : "#ffffff";
}

export type StudioTimelineProps = {
  tracks: StudioTrack[];
  clips: TimelineClip[];
  barWidth: number;
  barCount: number;
  secondsPerBar: number;
  /** Beats per bar, so a drag snaps to the project's meter (H-13). */
  beatsPerBar: number;
  duration: number;
  playhead: number;
  clock: (seconds: number) => string;
  rowStep: number;

  selectedTrack?: string | null;
  selectedClip: string | null;
  selectedIds: string[];
  drag: TimelineDrag | null;
  marquee: TimelineMarquee | null;
  loop: boolean;
  loopStart: number;
  loopEnd: number;
  viewWidth: number;
  viewLeft: number;
  /** Live geometry while a trim grip is dragged. */
  trimPreview?: { id: string; start: number; duration: number } | null;
  /** Live fade-in length while the fade handle is dragged. */
  fadePreview?: { id: string; fadeIn: number } | null;

  /** Receives the scroll container so the shell can measure the visible window. */
  timelineRef?: RefObject<HTMLDivElement | null>;
  onScroll: (left: number, width: number) => void;
  onLanePointerDown: (event: ReactPointerEvent<HTMLDivElement>) => void;
  /** Dragging a library song over a lane; preventDefault to allow the drop. */
  onLaneDragOver?: (event: ReactDragEvent<HTMLDivElement>) => void;
  /** Dropping a library song on a lane. */
  onLaneDrop?: (event: ReactDragEvent<HTMLDivElement>, trackId: string) => void;
  /** Clicking the bar ruler moves the playhead (the lanes are covered by clips). */
  onRulerSeek: (seconds: number) => void;
  onClipPointerDown: (event: ReactPointerEvent<HTMLButtonElement>, clip: TimelineClip, trackId: string) => void;
  onClipContextMenu: (event: React.MouseEvent<HTMLButtonElement>, clip: TimelineClip) => void;
  onTrimPointerDown: (
    event: ReactPointerEvent<HTMLElement>,
    clip: TimelineClip,
    edge: "start" | "end"
  ) => void;
  onFadePointerDown: (event: ReactPointerEvent<HTMLElement>, clip: TimelineClip) => void;  onLoopHandleDown: (event: ReactPointerEvent<HTMLButtonElement>) => void;
};

export function StudioTimeline(props: StudioTimelineProps) {
  const {
    tracks,
    clips,
    barWidth,
    barCount,
    secondsPerBar,
    beatsPerBar,
    duration,
    playhead,
    clock,
    rowStep,
    selectedTrack,
    selectedClip,
    selectedIds,
    drag,
    marquee,
    loop,
    loopStart,
    loopEnd,
    viewWidth,
    viewLeft,
    trimPreview,
    fadePreview,
    timelineRef,
    onScroll,
    onLanePointerDown,
    onLaneDragOver,
    onLaneDrop,
    onRulerSeek,
    onClipPointerDown,
    onClipContextMenu,
    onTrimPointerDown,
    onFadePointerDown,
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
      <div
        className="se-ruler-bars"
        aria-hidden="true"
        onPointerDown={(event) => {
          const inner = event.currentTarget.querySelector(".se-ruler-inner");
          if (!(inner instanceof HTMLElement)) return;
          const rect = inner.getBoundingClientRect();
          onRulerSeek(Math.max(0, ((event.clientX - rect.left) / barWidth) * secondsPerBar));
        }}
      >
        <div className="se-ruler-inner" style={{ width: barCount * barWidth }}>
          {Array.from({ length: barCount }).map((_, bar) => (
            <span key={`line-${bar}`} className="se-bar-line" style={{ left: bar * barWidth }} />
          ))}
          {Array.from({ length: barCount }).map((_, bar) => {
            // Labels thin out as the zoom drops so numbers never collide (S05/S19 show
            // every second bar at the captured zoom).
            const step = barWidth >= 80 ? 1 : barWidth >= 44 ? 2 : barWidth >= 24 ? 4 : 8;
            if (bar % step !== 0) return null;
            return (
              <span key={bar} className="se-bar-tick" style={{ left: bar * barWidth }}>
                {bar + 1}
              </span>
            );
          })}
          <span
            className="se-playhead-flag"
            style={{ left: (playhead / secondsPerBar) * barWidth }}
            aria-hidden="true"
          />
        </div>
      </div>

      <div className="se-lanes" onPointerDown={onLanePointerDown}>
        <div className="se-lanes-inner" style={{ width: barCount * barWidth }}>
          {tracks.map((track) => (
            <div
              key={track.id}
              className={`se-lane${selectedTrack === track.id ? " selected" : ""}`}
              style={{ height: rowStep }}
              onDragOver={onLaneDragOver}
              onDrop={onLaneDrop ? (event) => onLaneDrop(event, track.id) : undefined}
            >
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
                  const preview = trimPreview?.id === clip.id ? trimPreview : null;
                  const clipStart = preview ? preview.start : clip.start ?? 0;
                  const clipDuration = preview ? preview.duration : clip.duration ?? 4;
                  const dragOrigin = drag ? drag.origins[clip.id] : undefined;
                  const left =
                    isDragging && drag && dragOrigin !== undefined
                      ? (dragToStart(dragOrigin, drag.deltaPx, barWidth, secondsPerBar, beatsPerBar) /
                          secondsPerBar) *
                        barWidth
                      : (clipStart / secondsPerBar) * barWidth;
                  const width = Math.max(20, (clipDuration / secondsPerBar) * barWidth);
                  return (
                    <button
                      type="button"
                      key={clip.id}
                      className={`se-clip${isSelected ? " selected" : ""}${
                        isDragging ? " dragging" : ""
                      }${preview ? " trimming" : ""}`}
                      style={{
                        left,
                        width,
                        background: clip.color || track.color,
                        color: labelOn(clip.color || track.color),
                      }}
                      onPointerDown={(event) => onClipPointerDown(event, clip, track.id)}
                      onContextMenu={(event) => onClipContextMenu(event, clip)}
                      data-help="clip"
                      aria-pressed={isSelected}
                    >
                      <span className="se-clip-head">{clip.title || "Clip"}</span>
                      <span className="se-clip-body" aria-hidden="true">
                        {clip.audioUrl ? (
                          <Waveform
                            url={clip.audioUrl}
                            width={Math.max(20, Math.round(width))}
                            height={58}
                            label={`${clip.title || "Clip"} waveform`}
                            color="rgba(0,0,0,.34)"
                          />
                        ) : clip.midi?.notes?.length ? (
                          <span className="se-clip-midi">
                            {clip.midi.notes.map((note) => (
                              <span
                                key={note.id}
                                style={{
                                  left: `${(note.start / Math.max(0.01, clip.duration ?? 1)) * 100}%`,
                                  width: `${Math.max(1, (note.length / Math.max(0.01, clip.duration ?? 1)) * 100)}%`,
                                  top: `${
                                    ((MIDI_MAX_PITCH - note.pitch) /
                                      (MIDI_MAX_PITCH - MIDI_MIN_PITCH)) *
                                    100
                                  }%`,
                                }}
                              />
                            ))}
                          </span>
                        ) : null}
                      </span>
                      {isSelected ? (
                        <>
                          <span
                            className="se-trim se-trim-start"
                            aria-hidden="true"
                            onPointerDown={(event) => {
                              event.stopPropagation();
                              onTrimPointerDown(event, clip, "start");
                            }}
                          />
                          <span
                            className="se-trim se-trim-end"
                            aria-hidden="true"
                            onPointerDown={(event) => {
                              event.stopPropagation();
                              onTrimPointerDown(event, clip, "end");
                            }}
                          />
                          <span
                            className="se-fade-handle"
                            aria-hidden="true"
                            onPointerDown={(event) => {
                              event.stopPropagation();
                              onFadePointerDown(event, clip);
                            }}
                          />
                        </>
                      ) : null}
                      {(() => {
                        const fadeIn =
                          fadePreview?.id === clip.id
                            ? fadePreview.fadeIn
                            : clip.fadeIn ?? 0;
                        if (fadeIn <= 0 || clipDuration <= 0) return null;
                        return (
                          <span
                            className="se-fade"
                            aria-hidden="true"
                            style={{ width: `${Math.min(100, (fadeIn / clipDuration) * 100)}%` }}
                          />
                        );
                      })()}
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
                    beatsPerBar
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
          {Array.from({
            length: Math.ceil(duration / timeTickStep(barWidth, secondsPerBar)) + 1,
          }).map((_, index) => {
            const step = timeTickStep(barWidth, secondsPerBar);
            const at = index * step;
            if (at > duration) return null;
            return (
              <span
                key={index}
                className="se-time-tick"
                style={{ left: (at / secondsPerBar) * barWidth }}
              >
                {clock(at).slice(0, 5)}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
