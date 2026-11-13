"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Icon } from "@/components/Icon";
import { Waveform } from "@/components/studio/Waveform";
import {
  GAIN_DB_MAX,
  GAIN_DB_MIN,
  PITCH_MAX,
  PITCH_MIN,
  QUANTIZE_GRIDS,
  quantizeStep,
  sanitizeClipAudio,
  type ClipAudioSettings,
  type QuantizeGrid,
} from "@/lib/studio-clip-audio";
import { computePeaks } from "@/lib/studio-peaks";
import {
  WARP_MODES,
  generateWarpMarkers,
  moveWarpMarker,
  quantiseWarpMarkers,
  quantiseWarpMarkersToStep,
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
  /** Volume / Loop / Reverse / Pitch / Speed, parsed by `sanitizeClipAudio`. */
  audio?: unknown;
};

export type StudioAudioEditorProps = {
  clip: AudioEditorClip;
  secondsPerBar: number;
  beatsPerBar: number;
  /** Absolute transport position, so the playhead lands on the clip. */
  playhead: number;
  onWarp: (next: WarpState) => void;
  onAudio?: (next: ClipAudioSettings) => void;
  onClose: () => void;
};

const WAVE_HEIGHT = 150;
const MIN_WAVE_WIDTH = 720;

/** The captured readout prints a signed dB value with one decimal. */
function formatDb(value: number): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(1)} dB`;
}

export function StudioAudioEditor(props: StudioAudioEditorProps) {
  const { clip, secondsPerBar, beatsPerBar, playhead, onWarp, onAudio = () => {}, onClose } = props;
  const duration = Math.max(0.1, clip.duration ?? 4);
  const warp = useMemo(() => sanitizeWarp(clip.warp), [clip.warp]);
  const settings = useMemo(() => sanitizeClipAudio(clip.audio), [clip.audio]);
  const [peaks, setPeaks] = useState<number[] | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [quantizeGrid, setQuantizeGrid] = useState<QuantizeGrid>("1/8");
  const [triplets, setTriplets] = useState(false);
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
        return;
      }
      // SHIFT 1 / SHIFT 2 step the quantize grid finer / coarser (spec §36).
      const denser = event.shiftKey && (event.key === "1" || event.key === "!");
      const sparser = event.shiftKey && (event.key === "2" || event.key === "@");
      if (denser || sparser) {
        event.preventDefault();
        setQuantizeGrid((current) => {
          const index = QUANTIZE_GRIDS.findIndex((grid) => grid.value === current);
          const next = Math.max(
            0,
            Math.min(QUANTIZE_GRIDS.length - 1, index + (denser ? 1 : -1))
          );
          return QUANTIZE_GRIDS[next].value;
        });
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
          <label className="se-audio-volume">
            <span>Volume</span>
            <input
              type="range"
              min={GAIN_DB_MIN}
              max={GAIN_DB_MAX}
              step={0.5}
              value={settings.gainDb}
              aria-label="Volume"
              onChange={(event) =>
                onAudio({ ...settings, gainDb: Number(event.target.value) })
              }
            />
            <output>{formatDb(settings.gainDb)}</output>
          </label>

          <div className="se-audio-pair">
            <button
              type="button"
              aria-pressed={settings.loop}
              onClick={() => onAudio({ ...settings, loop: !settings.loop })}
            >
              <Icon name="fa-repeat" /> Loop
            </button>
            <button
              type="button"
              aria-pressed={settings.reverse}
              onClick={() => onAudio({ ...settings, reverse: !settings.reverse })}
            >
              <Icon name="fa-backward" /> Reverse
            </button>
          </div>

          <div className="se-audio-stepper">
            <span>Pitch</span>
            <button
              type="button"
              aria-label="Lower pitch"
              disabled={settings.pitch <= PITCH_MIN}
              onClick={() => onAudio({ ...settings, pitch: settings.pitch - 1 })}
            >
              −
            </button>
            <output>{settings.pitch > 0 ? `+${settings.pitch}` : settings.pitch}</output>
            <button
              type="button"
              aria-label="Raise pitch"
              disabled={settings.pitch >= PITCH_MAX}
              onClick={() => onAudio({ ...settings, pitch: settings.pitch + 1 })}
            >
              +
            </button>
          </div>

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

          <div className="se-audio-speed">
            <span>Speed</span>
            <button
              type="button"
              aria-pressed={settings.speed === 50}
              onClick={() =>
                onAudio({ ...settings, speed: settings.speed === 50 ? 100 : 50 })
              }
            >
              ×½
            </button>
            <button
              type="button"
              aria-pressed={settings.speed === 200}
              onClick={() =>
                onAudio({ ...settings, speed: settings.speed === 200 ? 100 : 200 })
              }
            >
              ×2
            </button>
            <output>{settings.speed}%</output>
          </div>

          <div className="se-audio-quantize">
            <span>Quantize</span>
            <div className="se-audio-grid" role="group" aria-label="Quantize grid">
              {QUANTIZE_GRIDS.map((grid) => (
                <button
                  key={grid.value}
                  type="button"
                  aria-pressed={quantizeGrid === grid.value}
                  onClick={() => setQuantizeGrid(grid.value)}
                >
                  {grid.label}
                </button>
              ))}
            </div>
            <div className="se-audio-quantize-actions">
              <button
                type="button"
                aria-pressed={triplets}
                onClick={() => setTriplets((value) => !value)}
              >
                Triplets
              </button>
              <button
                type="button"
                disabled={warp.markers.length === 0}
                onClick={() =>
                  onWarp({
                    ...warp,
                    markers: quantiseWarpMarkersToStep(
                      warp.markers,
                      quantizeStep(secondsPerBar, quantizeGrid, triplets)
                    ),
                  })
                }
              >
                Quantize
              </button>
            </div>
          </div>

          <p className="se-audio-hint">
            {warp.on
              ? `${warp.markers.length} markers · drag a head, Shift Q quantizes, Ctrl A selects all, Shift 1/2 sets the grid`
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
