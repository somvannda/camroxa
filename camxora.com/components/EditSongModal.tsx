"use client";

import { useState } from "react";

import { Icon } from "@/components/Icon";

export type EditKind =
  | "extend"
  | "crop"
  | "remove_section"
  | "reverse"
  | "adjust_speed"
  | "fade_in"
  | "fade_out"
  | "replace_section"
  | "sample";

export type EditPayload = {
  start_s?: number;
  end_s?: number;
  speed?: number;
  fade_seconds?: number;
  continue_at?: number;
  lyrics?: string;
  prompt?: string;
  title?: string;
};

const LABELS: Record<EditKind, string> = {
  extend: "Extend",
  crop: "Crop song",
  remove_section: "Remove section",
  reverse: "Reverse",
  adjust_speed: "Adjust speed",
  fade_in: "Fade in",
  fade_out: "Fade out",
  replace_section: "Replace section",
  sample: "Sample this song",
};

function fmt(seconds: number) {
  const total = Math.max(0, Math.round(seconds));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

/**
 * One dialog for Suno's Edit actions that need a value: a waveform-style
 * start/end selection, a continue point, a speed, a fade length, or the
 * replacement lyrics.
 */
export function EditSongModal({
  kind,
  title,
  duration,
  lyrics,
  busy = false,
  onClose,
  onSubmit,
}: {
  kind: EditKind;
  title: string;
  duration: number;
  lyrics?: string;
  busy?: boolean;
  onClose: () => void;
  onSubmit: (payload: EditPayload) => Promise<void> | void;
}) {
  const total = Math.max(1, Math.round(duration || 180));
  const [start, setStart] = useState(0);
  const [end, setEnd] = useState(Math.min(total, 30));
  const [continueAt, setContinueAt] = useState(total);
  const [speed, setSpeed] = useState(1.25);
  const [fade, setFade] = useState(3);
  const [nextLyrics, setNextLyrics] = useState(lyrics || "");
  const [prompt, setPrompt] = useState("");
  const [nextTitle, setNextTitle] = useState(`${title} (Sample)`);

  const isRange =
    kind === "crop" || kind === "remove_section" ||
    kind === "replace_section" || kind === "sample";
  const span = end - start;
  const rangeError =
    isRange && span < 1
      ? "Pick at least one second."
      : kind === "sample" && span > 30
        ? "Samples are limited to 30 seconds."
        : kind === "replace_section" && (span < 10 || span > 30)
          ? "Replace Section takes a 10–30 second window."
          : "";
  const canSubmit = !busy && !rangeError;

  function submit() {
    const payload: EditPayload = {};
    if (isRange) {
      payload.start_s = start;
      payload.end_s = end;
    }
    if (kind === "extend") payload.continue_at = continueAt;
    if (kind === "adjust_speed") payload.speed = speed;
    if (kind === "fade_in" || kind === "fade_out") payload.fade_seconds = fade;
    if (kind === "replace_section") {
      payload.lyrics = nextLyrics;
      payload.prompt = prompt;
    }
    if (kind === "sample") {
      payload.prompt = prompt;
      payload.title = nextTitle;
    }
    void onSubmit(payload);
  }

  return (
    <div
      className="s-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={LABELS[kind]}
      onClick={onClose}
    >
      <div
        className="s-modal"
        style={{ width: "min(520px,100%)" }}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="s-modal-head">
          <h3>{LABELS[kind]}</h3>
          <button
            type="button"
            className="s-btn s-btn-icon sm"
            aria-label="Close"
            onClick={onClose}
          >
            <Icon name="fa-xmark" />
          </button>
        </div>
        <div className="s-modal-body">
          <p className="s-note">{title} · {fmt(total)}</p>

          {isRange ? (
            <>
              <div className="s-note" aria-live="polite">
                {fmt(start)} → {fmt(end)} · {span.toFixed(1)}s selected
              </div>
              <input
                className="s-input"
                type="range"
                min={0}
                max={total}
                value={start}
                aria-label="Selection start"
                onChange={(event) => {
                  const value = Number(event.target.value);
                  setStart(value);
                  if (end <= value) setEnd(Math.min(total, value + 30));
                }}
              />
              <input
                className="s-input"
                type="range"
                min={0}
                max={total}
                value={end}
                aria-label="Selection end"
                onChange={(event) => {
                  const value = Number(event.target.value);
                  setEnd(value);
                  if (start >= value) setStart(Math.max(0, value - 30));
                }}
              />
              <div style={{ display: "flex", gap: 8 }}>
                <label className="s-note" style={{ flex: 1 }}>
                  Start (s)
                  <input
                    className="s-input"
                    type="number"
                    min={0}
                    max={total}
                    value={start}
                    onChange={(event) => setStart(Number(event.target.value))}
                  />
                </label>
                <label className="s-note" style={{ flex: 1 }}>
                  End (s)
                  <input
                    className="s-input"
                    type="number"
                    min={0}
                    max={total}
                    value={end}
                    onChange={(event) => setEnd(Number(event.target.value))}
                  />
                </label>
              </div>
            </>
          ) : null}

          {kind === "extend" ? (
            <label className="s-note">
              Continue at (s)
              <input
                className="s-input"
                type="number"
                min={0}
                max={total}
                value={continueAt}
                onChange={(event) => setContinueAt(Number(event.target.value))}
              />
            </label>
          ) : null}

          {kind === "adjust_speed" ? (
            <label className="s-note">
              Speed · {speed.toFixed(2)}×
              <input
                className="s-input"
                type="range"
                min={0.5}
                max={2}
                step={0.05}
                value={speed}
                onChange={(event) => setSpeed(Number(event.target.value))}
              />
            </label>
          ) : null}

          {kind === "fade_in" || kind === "fade_out" ? (
            <label className="s-note">
              Fade length · {fade}s
              <input
                className="s-input"
                type="range"
                min={1}
                max={10}
                value={fade}
                onChange={(event) => setFade(Number(event.target.value))}
              />
            </label>
          ) : null}

          {kind === "replace_section" ? (
            <>
              <label className="s-note">
                New lyrics for that section
                <textarea
                  className="s-input"
                  rows={5}
                  value={nextLyrics}
                  onChange={(event) => setNextLyrics(event.target.value)}
                />
              </label>
              <label className="s-note">
                Style hint (optional)
                <input
                  className="s-input"
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                />
              </label>
            </>
          ) : null}

          {kind === "sample" ? (
            <>
              <label className="s-note">
                What should grow out of this slice?
                <input
                  className="s-input"
                  value={prompt}
                  placeholder="e.g. warm lo-fi house with that vocal chop"
                  onChange={(event) => setPrompt(event.target.value)}
                />
              </label>
              <label className="s-note">
                Title
                <input
                  className="s-input"
                  value={nextTitle}
                  maxLength={200}
                  onChange={(event) => setNextTitle(event.target.value)}
                />
              </label>
            </>
          ) : null}

          {rangeError ? <p className="s-error">{rangeError}</p> : null}
        </div>
        <div className="s-modal-foot">
          <span style={{ flex: 1 }} />
          <button type="button" className="s-btn s-btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="s-btn s-btn-primary"
            disabled={!canSubmit}
            onClick={submit}
          >
            {busy ? "Working…" : kind === "sample" ? "Create sample" : LABELS[kind]}
          </button>
        </div>
      </div>
    </div>
  );
}
