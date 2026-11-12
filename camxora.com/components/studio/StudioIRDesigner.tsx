"use client";

import { useMemo, useState } from "react";

import { Icon } from "@/components/Icon";
import {
  designImpulseResponse,
  impulseEnvelope,
  saveCustomImpulseResponse,
  type ImpulseResponse,
} from "@/lib/studio-ir";

/**
 * Impulse Response Designer (reference settings > Content, advanced features).
 *
 * A small, honest designer: length and decay shape a synthetic impulse, the card
 * previews the same envelope the convolver will render, and Save adds it to the
 * Convolution picker under Custom.
 */

export type StudioIRDesignerProps = {
  onSave: (response: ImpulseResponse) => void;
  onClose: () => void;
};

const WIDTH = 320;
const HEIGHT = 80;

export function StudioIRDesigner({ onSave, onClose }: StudioIRDesignerProps) {
  const [name, setName] = useState("Custom hall");
  const [seconds, setSeconds] = useState(2.4);
  const [decay, setDecay] = useState(2.6);

  const preview = useMemo(
    () => designImpulseResponse({ name, seconds, decay }),
    [decay, name, seconds]
  );
  const envelope = impulseEnvelope(preview, 100);
  const points = envelope.map(
    (value, index) =>
      [
        (index / Math.max(1, envelope.length - 1)) * WIDTH,
        HEIGHT / 2 - value * (HEIGHT / 2 - 6),
      ] as const
  );
  const wave = points.length
    ? `M${points.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(" L")} L${points
        .slice()
        .reverse()
        .map(([x, y]) => `${x.toFixed(1)} ${(HEIGHT - y).toFixed(1)}`)
        .join(" L")} Z`
    : "";

  function save() {
    const response = designImpulseResponse({ name, seconds, decay });
    saveCustomImpulseResponse(response);
    onSave(response);
  }

  return (
    <div
      className="se-dialog-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Impulse response designer"
    >
      <div className="se-dialog">
        <h2>Impulse Response Designer</h2>
        <p className="se-dialog-note">
          Shape a synthetic impulse. Saved responses appear under Custom in the
          Convolution picker.
        </p>
        <svg
          className="sp-ir"
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          role="img"
          aria-label={`${preview.name} impulse preview`}
        >
          <line x1={0} x2={WIDTH} y1={HEIGHT / 2} y2={HEIGHT / 2} className="sp-ir-axis" />
          {wave ? <path d={wave} className="sp-ir-wave" /> : null}
        </svg>
        <label className="se-dialog-note" htmlFor="ir-name">
          Name
        </label>
        <input
          id="ir-name"
          className="se-pill"
          value={name}
          maxLength={60}
          onChange={(event) => setName(event.target.value)}
        />
        <label className="se-dialog-note" htmlFor="ir-length">
          Length <b>{seconds.toFixed(1)}s</b>
        </label>
        <input
          id="ir-length"
          type="range"
          min={0.2}
          max={5}
          step={0.1}
          value={seconds}
          onChange={(event) => setSeconds(Number(event.target.value))}
        />
        <label className="se-dialog-note" htmlFor="ir-decay">
          Decay <b>{decay.toFixed(1)}</b>
        </label>
        <input
          id="ir-decay"
          type="range"
          min={0.5}
          max={6}
          step={0.1}
          value={decay}
          onChange={(event) => setDecay(Number(event.target.value))}
        />
        <div className="se-dialog-foot">
          <button type="button" className="se-pill" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="se-pill on" onClick={save}>
            <Icon name="fa-check" /> Save response
          </button>
        </div>
      </div>
    </div>
  );
}
