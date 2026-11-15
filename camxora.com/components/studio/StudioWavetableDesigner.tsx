"use client";

import { useMemo, useState } from "react";

import { Icon } from "@/components/Icon";
import {
  nextWavetableId,
  sanitizeHarmonics,
  WAVETABLE_PARTIALS,
  WAVETABLE_PRESETS,
  wavetableSamples,
  type CustomWavetable,
} from "@/lib/studio-wavetable";

/**
 * Wavetable Designer (N-14).
 *
 * Hidden entirely unless Content → Advanced content features is on, matching the
 * captured settings copy ("Off, the menu items that open them are hidden").
 */

export type StudioWavetableDesignerProps = {
  onSave: (table: CustomWavetable) => void;
  onClose: () => void;
  /** Prefill from an existing design when editing. */
  initial?: CustomWavetable | null;
};

export function StudioWavetableDesigner({ onSave, onClose, initial = null }: StudioWavetableDesignerProps) {
  const [name, setName] = useState(initial?.name ?? "My wavetable");
  const [harmonics, setHarmonics] = useState<number[]>(() =>
    sanitizeHarmonics(initial?.harmonics ?? WAVETABLE_PRESETS[0].harmonics)
  );

  const path = useMemo(() => {
    const samples = wavetableSamples(harmonics, 200);
    return samples
      .map((value, index) => `${index === 0 ? "M" : "L"}${index} ${50 - value * 40}`)
      .join(" ");
  }, [harmonics]);

  function setPartial(index: number, value: number) {
    setHarmonics((current) => current.map((entry, at) => (at === index ? value : entry)));
  }

  return (
    <div
      className="se-dialog-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Wavetable designer"
    >
      <div className="se-dialog se-wavetable-dialog">
        <h2>Wavetable Designer</h2>
        <p className="se-dialog-note">
          Shape the sine partials of a synth voice, then save it as an instrument for MIDI
          clips in this project.
        </p>

        <div className="se-wavetable-preview" aria-hidden="true">
          <svg viewBox="0 0 200 100" preserveAspectRatio="none">
            <path d={path} />
          </svg>
        </div>

        <div className="se-wavetable-presets" role="group" aria-label="Wavetable shapes">
          {WAVETABLE_PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              className="se-pill"
              onClick={() => setHarmonics(sanitizeHarmonics(preset.harmonics))}
            >
              {preset.name}
            </button>
          ))}
        </div>

        <div className="se-wavetable-partials">
          {Array.from({ length: WAVETABLE_PARTIALS }, (_, index) => (
            <label key={index} className="se-wavetable-partial">
              <input
                type="range"
                min={0}
                max={100}
                step={1}
                value={Math.round((harmonics[index] ?? 0) * 100)}
                aria-label={`Partial ${index + 1}`}
                onChange={(event) => setPartial(index, Number(event.target.value) / 100)}
              />
              <span>{index + 1}</span>
            </label>
          ))}
        </div>

        <label className="se-dialog-note" htmlFor="se-wavetable-name">
          Name
        </label>
        <input
          id="se-wavetable-name"
          className="se-pill"
          value={name}
          aria-label="Wavetable name"
          onChange={(event) => setName(event.target.value)}
        />

        <div className="se-dialog-foot">
          <button type="button" className="se-pill" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="se-pill on"
            onClick={() =>
              onSave({
                id: initial?.id ?? nextWavetableId(),
                name: name.trim() || "Wavetable",
                harmonics: sanitizeHarmonics(harmonics),
              })
            }
          >
            <Icon name="fa-check" /> Save wavetable
          </button>
        </div>
      </div>
    </div>
  );
}
