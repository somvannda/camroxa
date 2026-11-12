"use client";

import { useMemo, useRef } from "react";

import { Icon } from "@/components/Icon";
import {
  sanitizeAutomation,
  type AutomationPoint,
} from "@/lib/studio-automation";
import type { StudioTrack } from "@/lib/studio-tracks";

/**
 * Track automation panel (reference §20 "Automation").
 *
 * The first slice is the captured track volume curve: a value lane over the project
 * timeline. Click adds a point, double-click removes one, and the same points drive
 * playback and export. Pan and plugin-parameter lanes can join later without changing
 * this document model.
 */

export type StudioAutomationPanelProps = {
  track: StudioTrack;
  duration: number;
  playhead: number;
  onChange: (points: AutomationPoint[]) => void;
  onClose: () => void;
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
  const laneRef = useRef<HTMLDivElement | null>(null);
  const points = useMemo(
    () => sanitizeAutomation(track.volumeAutomation, 0, 100),
    [track.volumeAutomation]
  );
  const span = Math.max(1, duration);

  function addPoint(event: React.PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    const lane = laneRef.current;
    if (!lane) return;
    const rect = lane.getBoundingClientRect();
    const time = Math.max(0, Math.min(span, ((event.clientX - rect.left) / rect.width) * span));
    const value = Math.max(0, Math.min(100, (1 - (event.clientY - rect.top) / rect.height) * 100));
    const next = [
      ...points,
      { id: `auto-${Date.now().toString(36)}`, time: Number(time.toFixed(3)), value: Math.round(value) },
    ].sort((a, b) => a.time - b.time);
    onChange(next);
  }

  function removePoint(id: string) {
    onChange(points.filter((point) => point.id !== id));
  }

  const line = points
    .map((point) => `${(point.time / span) * 100},${100 - point.value}`)
    .join(" ");

  return (
    <section className="se-automation" aria-label="Track automation">
      <header className="se-automation-head">
        <span>
          <Icon name="fa-bezier-curve" /> {track.name} - Volume
        </span>
        <button
          type="button"
          className="se-pill"
          disabled={points.length === 0}
          onClick={() => onChange([])}
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
        aria-label="Volume automation lane"
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
              bottom: `${point.value}%`,
            }}
            aria-label={`Volume ${point.value} at ${formatSeconds(point.time)}`}
            title={`Volume ${point.value} at ${formatSeconds(point.time)} (double-click to remove)`}
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
        <span className="se-automation-caption">Click to add a point - double-click a point to remove</span>
      </div>
    </section>
  );
}
