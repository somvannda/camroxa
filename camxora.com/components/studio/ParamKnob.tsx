"use client";

import type { CSSProperties } from "react";

/**
 * Shared parameter knob used by the plugin cards (S40/S42/S48): a circular dial with a
 * product-accent arc and a pointer, backed by a transparent range input so keyboard and
 * screen readers keep working. Frequency params use a log scale for the arc.
 */

export type ParamKnobProps = {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit?: string;
  log?: boolean;
  disabled?: boolean;
  /** Optional short value text override (e.g. note names). */
  display?: string;
  onChange: (value: number) => void;
};

function formatValue(value: number, unit?: string, percent01 = false): string {
  if (percent01) return `${Math.round(value * 100)}%`;
  if (unit === "hz") {
    return value >= 1000 ? `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}khz` : `${Math.round(value)}hz`;
  }
  if (unit === "db") return `${Math.round(value * 10) / 10}db`;
  if (unit === "ms") return `${Math.round(value)}ms`;
  if (unit === "s") return `${(Math.round(value * 10) / 10).toFixed(1)}s`;
  if (unit === "%") return `${Math.round(value)}%`;
  return `${Math.round(value * 10) / 10}`;
}

export function ParamKnob(props: ParamKnobProps) {
  const { label, value, min, max, step, unit, log, disabled, display, onChange } = props;
  // Suno-authored percent controls store 0–1 but read as 0–100 %.
  const percent01 = unit === "%" && min === 0 && max === 1;
  const pct = log
    ? Math.min(
        1,
        Math.max(
          0,
          (Math.log(Math.max(1, value)) - Math.log(min)) / (Math.log(max) - Math.log(min))
        )
      )
    : Math.min(1, Math.max(0, (value - min) / (max - min)));
  const text = display ?? formatValue(value, unit, percent01);
  return (
    <label className="sp-knob">
      <span
        className="sp-knob-dial"
        style={{ ["--p" as string]: `${(pct * 270).toFixed(1)}deg` } as CSSProperties}
        aria-hidden="true"
      >
        <span
          className="sp-knob-pointer"
          style={{ transform: `rotate(${(-135 + pct * 270).toFixed(1)}deg)` }}
        />
      </span>
      <input
        className="sp-knob-input"
        type="range"
        min={min}
        max={max}
        step={percent01 ? 0.01 : step}
        value={value}
        aria-label={label}
        aria-valuetext={text}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <span className="sp-knob-label">{label}</span>
      <span className="sp-knob-readout">{text}</span>
    </label>
  );
}
