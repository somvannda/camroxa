"use client";

import { useMemo, useRef, useState } from "react";

import { Icon } from "@/components/Icon";
import {
  sanitizeAutomation,
  type AutomationLane,
  type AutomationPoint,
} from "@/lib/studio-automation";
import type { StudioTrack } from "@/lib/studio-tracks";

/**
 * Track automation panel (reference §20 "Automation").
 *
 * Volume and pan are the first captured lanes: both are value curves over the project
 * timeline, and the same points drive playback and export. Click adds a point,
 * double-click removes one, and the lane switch changes which curve is edited.
 */

export type StudioAutomationPanelProps = {
  track: StudioTrack;
  duration: number;
  playhead: number;
  onChange: (lane: AutomationLane, points: AutomationPoint[]) => void;
  onClose: () => void;
};

const RANGES: Record<AutomationLane, { min: number; max: number; label: string }> = {
  volume: { min: 0, max: 100, label: "Volume" },
  pan: { min: -100, max: 100, label: "Pan" },
};

function formatSeconds(value: number): string {
  return `${value.toFixed(2)}s`;
}

export function StudioAutomationPanel({
  track,
  duration,
  playhead,
  onChange,
  onClose,
}: StudioAutomationPanelProps) {
  const [lane, setLane] = useState<AutomationLane>("volume");
  const laneRef = useRef<HTMLDivElement | null>(null);
  const range = RANGES[lane];
  const points = useMemo(
    () =>
      sanitizeAutomation(
        lane === "volume" ? track.volumeAutomation : track.panAutomation,
        range.min,
        range.max
      ),
    [lane, range.max, range.min, track.panAutomation, track.volumeAutomation]
  );
  const span = Math.max(1, duration);
  const heightOf = (value: number) =>
    100 - ((value - range.min) / (range.max - range.min)) * 100;

  function addPoint(event: React.PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    const element = laneRef.current;
    if (!element) return;
    const rect = element.getBoundingClientRect();
    const time = Math.max(0, Math.min(span, ((event.clientX - rect.left) / rect.width) * span));
    const ratio = 1 - (event.clientY - rect.top) / rect.height;
    const value = range.min + Math.max(0, Math.min(1, ratio)) * (range.max - range.min);
    const next = [
      ...points,
      {
        id: `auto-${Date.now().toString(36)}`,
        time: Number(time.toFixed(3)),
        value: Math.round(value),
      },
    ].sort((a, b) => a.time - b.time);
    onChange(lane, next);
  }

  function removePoint(id: string) {
    onChange(lane, points.filter((point) => point.id !== id));
  }

  const line = points
    .map((point) => `${(point.time / span) * 100},${heightOf(point.value)}`)
    .join(" ");

  return (
    <section className="se-automation" aria-label="Track automation">
      <header className="se-automation-head">
        <span>
          <Icon name="fa-bezier-curve" /> {track.name}
        </span>
        <span className="se-automation-tabs" role="group" aria-label="Automation lane">
          {(["volume", "pan"] as const).map((value) => (
            <button
              key={value}
              type="button"
              className={`se-pill${lane === value ? " on" : ""}`}
              aria-pressed={lane === value}
              onClick={() => setLane(value)}
            >
              {RANGES[value].label}
            </button>
          ))}
        </span>
        <button
          type="button"
          className="se-pill"
          disabled={points.length === 0}
          onClick={() => onChange(lane, [])}
        >
          Clear
        </button>
        <button type="button" className="se-pill" aria-label="Close automation" onClick={onClose}>
          <Icon name="fa-xmark" />
        </button>
      </header>
      <div
        className="se-automation-lane"
        ref={laneRef}
        role="group"
        aria-label={`${range.label} automation lane`}
        onPointerDown={addPoint}
      >
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          {points.length > 1 ? <polyline points={line} className="se-automation-line" /> : null}
        </svg>
        {points.map((point) => (
          <button
            key={point.id}
            type="button"
            className="se-automation-point"
            style={{
              left: `${(point.time / span) * 100}%`,
              bottom: `${100 - heightOf(point.value)}%`,
            }}
            aria-label={`${range.label} ${point.value} at ${formatSeconds(point.time)}`}
            title={`${range.label} ${point.value} at ${formatSeconds(point.time)} (double-click to remove)`}
            onPointerDown={(event) => event.stopPropagation()}
            onDoubleClick={(event) => {
              event.stopPropagation();
              removePoint(point.id);
            }}
          />
        ))}
        <span
          className="se-automation-playhead"
          style={{ left: `${(Math.max(0, Math.min(span, playhead)) / span) * 100}%` }}
          aria-hidden="true"
        />
        <span className="se-automation-caption">
          Click to add a {range.label.toLowerCase()} point - double-click a point to remove
        </span>
      </div>
    </section>
  );
}
