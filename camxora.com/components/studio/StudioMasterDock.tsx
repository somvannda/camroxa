"use client";

import { useState } from "react";

import { Icon } from "@/components/Icon";
import { ParamKnob } from "@/components/studio/ParamKnob";
import {
  applyMasterPreset,
  LIMITER_DEFAULTS,
  LIMITER_PARAMS,
  MASTER_PRESETS,
  type MasterChainEntry,
  type MasterPreset,
} from "@/lib/studio-master-bus";

/**
 * Master chain dock (S48).
 *
 * Clicking Main swaps the plugin dock for the master chain: the captured Limiter card
 * (Lookahead / Pre Gain / Attack / Release / Link) plus the capture's Add effect rail
 * with EQ / Compressor suggestions. EQ and Compressor are real master links
 * (one Amount knob). Reverb is not offered: Suno's master signal chain only
 * carries limiter/EQ/compressor (D-034), so a master reverb would be local-only.
 */

function nextId(type: string) {
  return `master-${type}-${Date.now().toString(36)}`;
}

export function StudioMasterDock({
  chain,
  onChange,
}: {
  chain: MasterChainEntry[];
  onChange: (next: MasterChainEntry[]) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [presetOpen, setPresetOpen] = useState(false);

  const indexOf = (type: string) =>
    chain.findIndex((entry) => (entry.type ?? "").toLowerCase().includes(type));

  function add(type: "limiter" | "eq" | "compressor") {
    const entry: MasterChainEntry =
      type === "limiter"
        ? { id: nextId("limiter"), type, enabled: true, params: { ...LIMITER_DEFAULTS } }
        : { id: nextId(type), type, enabled: true, amount: 0.5 };
    onChange([...chain, entry]);
    setMenuOpen(false);
  }

  function removeAt(index: number) {
    onChange(chain.filter((_, position) => position !== index));
  }

  function setLimiterParam(index: number, key: string, value: number) {
    onChange(
      chain.map((entry, position) =>
        position === index
          ? { ...entry, params: { ...LIMITER_DEFAULTS, ...(entry.params ?? {}), [key]: value } }
          : entry
      )
    );
  }

  function setAmount(index: number, value: number) {
    onChange(
      chain.map((entry, position) =>
        position === index ? { ...entry, amount: Math.min(1, Math.max(0, value / 100)) } : entry
      )
    );
  }

  function applyPreset(preset: MasterPreset) {
    onChange(applyMasterPreset(chain, preset));
    setPresetOpen(false);
  }

  const hasLimiter = indexOf("limit") >= 0;

  return (
    <section className="sp-dock" aria-label="Master chain">
      <div className="sp-rail">
        {chain.map((entry, index) => {
          const type = (entry.type ?? "").toLowerCase();
          if (type.includes("limit")) {
            const params: Record<string, number> = { ...LIMITER_DEFAULTS, ...(entry.params ?? {}) };
            return (
              <article
                key={entry.id ?? `limiter-${index}`}
                className="sp-slot sp-limiter-card"
                aria-label="Limiter slot"
              >
                <header className="sp-slot-head">
                  <span className="sp-dot" aria-hidden="true" />
                  <strong>Limiter</strong>
                  <span className="sp-preset-wrap">
                    <button
                      type="button"
                      className="sp-preset"
                      aria-expanded={presetOpen}
                      aria-haspopup="menu"
                      title="Master presets"
                      onClick={() => setPresetOpen((current) => !current)}
                    >
                      Default
                    </button>
                    {presetOpen ? (
                      <span className="sp-preset-menu" role="menu" aria-label="Master presets">
                        {MASTER_PRESETS.map((preset) => (
                          <button
                            key={preset.id}
                            type="button"
                            role="menuitem"
                            onClick={() => applyPreset(preset)}
                          >
                            {preset.name}
                          </button>
                        ))}
                      </span>
                    ) : null}
                  </span>
                  <span className="sp-slot-tools">
                    <button
                      type="button"
                      aria-label="Remove Limiter"
                      onClick={() => removeAt(index)}
                    >
                      <Icon name="fa-xmark" />
                    </button>
                  </span>
                </header>
                <div className="sp-knobs sp-knob-grid sp-limiter-knobs">
                  {LIMITER_PARAMS.map((param) => (
                    <ParamKnob
                      key={param.key}
                      label={param.label}
                      value={params[param.key] ?? param.default}
                      min={param.min}
                      max={param.max}
                      step={param.max > 100 ? 1 : 0.1}
                      unit={param.unit}
                      display={
                        param.key === "link" ? ((params[param.key] ?? 1) >= 0.5 ? "On" : "Off") : undefined
                      }
                      onChange={(value) => setLimiterParam(index, param.key, value)}
                    />
                  ))}
                </div>
              </article>
            );
          }
          const label = type.includes("eq") ? "EQ" : "Compressor";
          return (
            <article key={entry.id ?? `${type}-${index}`} className="sp-slot" aria-label={`${label} slot`}>
              <header className="sp-slot-head">
                <span className="sp-dot" aria-hidden="true" />
                <strong>{label}</strong>
                <span className="sp-preset-wrap">
                  <button type="button" className="sp-preset" disabled>
                    Default
                  </button>
                </span>
                <span className="sp-slot-tools">
                  <button type="button" aria-label={`Remove ${label}`} onClick={() => removeAt(index)}>
                    <Icon name="fa-xmark" />
                  </button>
                </span>
              </header>
              <div className="sp-knobs sp-knob-grid">
                <ParamKnob
                  label="Amount"
                  value={(entry.amount ?? 0.5) * 100}
                  min={0}
                  max={100}
                  step={1}
                  unit="%"
                  onChange={(value) => setAmount(index, value)}
                />
              </div>
            </article>
          );
        })}

        <div className="sp-empty-rail" aria-label="Add another effect">
          <button
            type="button"
            className="sp-add"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <Icon name="fa-plus" /> Add effect
          </button>
          <div className="sp-ghosts">
            {([
              { type: "eq", label: "EQ" },
              { type: "compressor", label: "Compressor" },
            ] as const).map((ghost) => (
              <button
                key={ghost.type}
                type="button"
                className="sp-ghost"
                title={`Add ${ghost.label} to the master`}
                aria-label={`Add ${ghost.label}`}
                onClick={() => add(ghost.type)}
              >
                <span className="sp-ghost-label">{ghost.label}</span>
              </button>
            ))}
          </div>
          {menuOpen ? (
            <div className="sp-ir-menu" role="menu" aria-label="Add master effect" style={{ left: 16, top: 16 }}>
              {hasLimiter ? (
                <button type="button" role="menuitem" disabled>
                  Limiter (already added)
                </button>
              ) : (
                <button type="button" role="menuitem" onClick={() => add("limiter")}>
                  Limiter
                </button>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
