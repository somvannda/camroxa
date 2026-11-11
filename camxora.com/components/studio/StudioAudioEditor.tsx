"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Icon } from "@/components/Icon";
import { Waveform } from "@/components/studio/Waveform";
import { computePeaks } from "@/lib/studio-peaks";
import {
  WARP_MODES,
  generateWarpMarkers,
  moveWarpMarker,
  quantiseWarpMarkers,
  sanitizeWarp,
  type WarpMarker,
  type WarpMode,
  type WarpState,
} from "@/lib/studio-warp";

/**
 * Audio clip editor (S30, spec §81/§97): the captured "Clip Settings" column beside a
 * zoomed waveform that carries the warp markers.
 *
 * Built to the capture rather than invented: the Stretch switch, the three modes with
 * their captured tooltips, and the Formant control are the whole settings column for
 * now — Volume/Loop/Reverse/Pitch/Speed/Quantize from §81 belong to the audio-settings
 * pass and are deliberately absent instead of being dead controls.
 *
 * Markers are white pennant heads on the waveform's top edge with a hairline stem, one
 * per marker, clipped to the clip's bounds (S30-warp-markers).
 */

export type AudioEditorClip = {
  id: string;
  title?: string;
  color?: string;
  start?: number;
  duration?: number;
  offset?: number;
  audioUrl?: string | null;
  warp?: unknown;
};

export type StudioAudioEditorProps = {
  clip: AudioEditorClip;
  secondsPerBar: number;
  beatsPerBar: number;
  /** Absolute transport position, so the playhead lands on the clip. */
  playhead: number;
  onWarp: (next: WarpState) => void;
  onClose: () => void;
};

const WAVE_HEIGHT = 150;
const MIN_WAVE_WIDTH = 720;

export function StudioAudioEditor(props: StudioAudioEditorProps) {
  const { clip, secondsPerBar, beatsPerBar, playhead, onWarp, onClose } = props;
  const duration = Math.max(0.1, clip.duration ?? 4);
  const warp = useMemo(() => sanitizeWarp(clip.warp), [clip.warp]);
  const [peaks, setPeaks] = useState<number[] | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [preview, setPreview] = useState<WarpMarker[] | null>(null);
  const previewRef = useRef<WarpMarker[] | null>(null);
  const dragRef = useRef<{ id: string; startX: number; origin: number } | null>(null);
  const waveRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let active = true;
    if (!clip.audioUrl) {
      setPeaks(null);
      return;
    }
    void computePeaks(clip.audioUrl).then((next) => {
      if (active) setPeaks(next);
    });
    return () => {
      active = false;
    };
  }, [clip.audioUrl]);

  const markers = preview ?? warp.markers;
  const width = Math.max(MIN_WAVE_WIDTH, Math.round(duration * 80));
  const clipStart = clip.start ?? 0;
  const playheadLeft = Math.max(0, Math.min(1, (playhead - clipStart) / duration)) * 100;

  function writeWarp(next: Partial<WarpState>, regenerate?: WarpMode) {
    const mode = regenerate ?? warp.mode;
    const nextMarkers = regenerate
      ? generateWarpMarkers({
          mode: regenerate,
          duration,
          secondsPerBar,
          beatsPerBar,
          offset: clip.offset ?? 0,
          peaks,
        })
      : warp.markers;
    setSelected([]);
    setPreview(null);
    onWarp({ ...warp, ...next, mode, markers: nextMarkers });
  }

  /** Selecting a mode fills the clip with that mode's markers (spec §94). */
  function chooseMode(mode: WarpMode) {
    writeWarp({ on: true }, mode);
  }

  function toggleStretch() {
    if (warp.on) {
      onWarp({ ...warp, on: false });
      return;
    }
    if (warp.markers.length === 0) {
      writeWarp({ on: true }, warp.mode);
      return;
    }
    onWarp({ ...warp, on: true });
  }

  /** Drag a marker head: the timeline position moves, the source position does not. */
  useEffect(() => {
    const move = (event: PointerEvent) => {
      const session = dragRef.current;
      if (!session) return;
      const rect = waveRef.current?.getBoundingClientRect();
      if (!rect || rect.width === 0) return;
      const delta = ((event.clientX - session.startX) / rect.width) * duration;
      const next = moveWarpMarker(warp.markers, session.id, session.origin + delta, duration);
      previewRef.current = next;
      setPreview(next);
    };
    const up = () => {
      const session = dragRef.current;
      if (!session) return;
      dragRef.current = null;
      const next = previewRef.current;
      previewRef.current = null;
      setPreview(null);
      if (next) onWarp({ ...warp, markers: next });
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
    };
  });

  /** The panel owns the marker shortcuts while it is open (spec §36). */
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)
      ) {
        return;
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "a") {
        event.preventDefault();
        setSelected(warp.markers.map((marker) => marker.id));
        return;
      }
      if (event.shiftKey && event.key.toLowerCase() === "q") {
        event.preventDefault();
        const ids = selected.length ? selected : warp.markers.map((marker) => marker.id);
        const untouched = warp.markers.filter((marker) => !ids.includes(marker.id));
        const snapped = quantiseWarpMarkers(
          warp.markers.filter((marker) => ids.includes(marker.id)),
          secondsPerBar,
          beatsPerBar
        );
        onWarp({
          ...warp,
          markers: [...untouched, ...snapped].sort((a, b) => a.time - b.time),
        });
        setSelected([]);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [warp, selected, secondsPerBar, beatsPerBar, onWarp]);

  const bars = Math.max(1, Math.ceil(duration / secondsPerBar));
  const firstBar = Math.floor(clipStart / secondsPerBar);

  return (
    <section className="se-audio" aria-label="Clip settings">
      <header className="se-audio-head">
        <strong>Clip Settings</strong>
        <button type="button" className="se-icon" aria-label="Close clip editor" onClick={onClose}>
          <Icon name="fa-xmark" />
        </button>
      </header>

      <div className="se-audio-body">
        <div className="se-audio-settings">
          <div className="se-audio-title">
            <span>Stretch</span>
            <button
              type="button"
              role="switch"
              aria-checked={warp.on}
              aria-label="Stretch"
              className={`se-audio-switch${warp.on ? " on" : ""}`}
              onClick={toggleStretch}
            >
              <span />
            </button>
          </div>

          <div className="se-audio-modes" role="radiogroup" aria-label="Stretch mode">
            {WARP_MODES.map((mode) => (
              <button
                key={mode.value}
                type="button"
                role="radio"
                aria-checked={warp.on && warp.mode === mode.value}
                className={warp.on && warp.mode === mode.value ? "on" : ""}
                title={mode.hint}
                onClick={() => chooseMode(mode.value)}
              >
                <Icon
                  name={
                    mode.value === "beat"
                      ? "fa-music"
                      : mode.value === "transients"
                        ? "fa-wave-square"
                        : "fa-arrows-left-right"
                  }
                />
                {mode.label}
              </button>
            ))}
          </div>

          <label className="se-audio-formant">
            <span>Formant</span>
            <input
              type="range"
              min={0}
              max={100}
              step={1}
              value={warp.formant}
              aria-label="Formant"
              onChange={(event) => onWarp({ ...warp, formant: Number(event.target.value) })}
            />
            <output>{warp.formant}%</output>
          </label>

          <p className="se-audio-hint">
            {warp.on
              ? `${warp.markers.length} markers · drag a head, Shift Q quantizes, Ctrl A selects all`
              : "Stretch is off — choose a mode to place markers"}
          </p>
        </div>

        <div className="se-audio-canvas">
          <div className="se-audio-ruler" style={{ width }}>
            {Array.from({ length: bars }).map((_, index) => (
              <span
                key={index}
                className="se-audio-tick"
                style={{ left: ((index * secondsPerBar) / duration) * width }}
              >
                {firstBar + index + 1}
              </span>
            ))}
          </div>
          <div className="se-audio-scroll">
            <div className="se-audio-wave" ref={waveRef} style={{ width, height: WAVE_HEIGHT }}>
              <Waveform
                url={clip.audioUrl}
                width={width}
                height={WAVE_HEIGHT}
                label={`${clip.title || "Clip"} waveform`}
                color={clip.color || "#52d17c"}
              />
              {warp.on
                ? markers.map((marker) => (
                    <span
                      key={marker.id}
                      className={`se-warp-marker${selected.includes(marker.id) ? " selected" : ""}`}
                      style={{ left: `${(marker.time / duration) * 100}%` }}
                    >
                      <button
                        type="button"
                        className="se-warp-head"
                        aria-label={`Warp marker at ${marker.time.toFixed(2)} seconds`}
                        aria-pressed={selected.includes(marker.id)}
                        onPointerDown={(event) => {
                          event.stopPropagation();
                          dragRef.current = {
                            id: marker.id,
                            startX: event.clientX,
                            origin: marker.time,
                          };
                        }}
                        onClick={(event) => {
                          event.stopPropagation();
                          // Clicking selects; quantize acts on the selection. Dragging a
                          // head keeps it selected, so the moved marker is included too.
                          setSelected((current) =>
                            current.includes(marker.id) ? current : [...current, marker.id]
                          );
                        }}
                      />
                      <span className="se-warp-stem" aria-hidden="true" />
                    </span>
                  ))
                : null}
              <span
                className="se-audio-playhead"
                style={{ left: `${playheadLeft}%` }}
                aria-hidden="true"
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
