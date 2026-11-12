"use client";

import { useMemo, useState } from "react";

import { Icon } from "@/components/Icon";
import {
  WAVETABLE_HARMONICS,
  designWavetable,
  saveCustomWavetable,
  wavetablePreview,
  type Wavetable,
} from "@/lib/studio-wavetable";

/**
 * Wavetable Designer (reference settings > Content): edit the first eight partials,
 * preview the resulting waveform, save it to the custom table library, and select it
 * on the MIDI clip.
 */

export type StudioWavetableDesignerProps = {
  onSave: (table: Wavetable) => void;
  onClose: () => void;
};

const WIDTH = 320;
const HEIGHT = 80;

export function StudioWavetableDesigner({ onSave, onClose }: StudioWavetableDesignerProps) {
  const [name, setName] = useState("Custom table");
  const [harmonics, setHarmonics] = useState<number[]>(() =>
    Array.from({ length: WAVETABLE_HARMONICS }, (_, index) => (index === 0 ? 1 : 0))
  );

  const preview = useMemo(
    () => designWavetable({ name, harmonics }),
    [harmonics, name]
  );
  const samples = wavetablePreview(preview, 100);
  const points = samples.map(
    (value, index) =>
      [
        (index / Math.max(1, samples.length - 1)) * WIDTH,
        HEIGHT / 2 - value * (HEIGHT / 2 - 6),
      ] as const
  );
  const path = points.length
    ? `M${points.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(" L")}`
    : "";

  function save() {
    const table = designWavetable({ name, harmonics });
    saveCustomWavetable(table);
    onSave(table);
  }

  return (
    <div
      className="se-dialog-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Wavetable designer"
    >
      <div className="se-dialog">
        <h2>Wavetable Designer</h2>
        <p className="se-dialog-note">
          Shape the first eight partials. Saved tables appear in the MIDI editor's Table
          picker.
        </p>
        <svg
          className="sp-ir"
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          role="img"
          aria-label={`${preview.name} wavetable preview`}
        >
          <line x1={0} x2={WIDTH} y1={HEIGHT / 2} y2={HEIGHT / 2} className="sp-ir-axis" />
          {path ? <path d={path} className="sp-ir-wave" /> : null}
        </svg>
        <label className="se-dialog-note" htmlFor="wavetable-name">
          Name
        </label>
        <input
          id="wavetable-name"
          className="se-pill"
          value={name}
          maxLength={60}
          onChange={(event) => setName(event.target.value)}
        />
        <div className="se-wavetable-harmonics" role="group" aria-label="Harmonics">
          {harmonics.map((value, index) => (
            <label key={index}>
              <input
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={value}
                aria-label={`Harmonic ${index + 1}`}
                onChange={(event) =>
                  setHarmonics((current) =>
                    current.map((item, position) =>
                      position === index ? Number(event.target.value) : item
                    )
                  )
                }
              />
              <span>{index + 1}</span>
            </label>
          ))}
        </div>
        <div className="se-dialog-foot">
          <button type="button" className="se-pill" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="se-pill on" onClick={save}>
            <Icon name="fa-check" /> Save table
          </button>
        </div>
      </div>
    </div>
  );
}
