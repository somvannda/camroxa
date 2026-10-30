"use client";

import { useMemo, useState } from "react";

import { Icon } from "@/components/Icon";
import {
  STUDIO_PLUGINS,
  getPlugin,
  type PluginChainEntry,
  type PluginId,
} from "@/lib/studio-plugins";
import {
  addPlugin,
  commitPreset,
  movePlugin,
  removePlugin,
  setMode,
  setParam,
  toggleBypass,
  togglePoppedOut,
} from "@/lib/studio-plugin-chain";

type Props = {
  chain: PluginChainEntry[];
  onChange: (next: PluginChainEntry[]) => void;
  /** Track name, shown in the dock header. */
  trackName?: string;
};

/**
 * Plugin chain dock.
 *
 * Mirrors the reference layout (spec §50): one panel per plugin, laid out in a
 * horizontally scrollable rail, each with a header (colour dot, name, preset,
 * Update-when-dirty, popout, close) and a parameter grid.
 *
 * Knobs render as labelled sliders for now; the reference uses rotary knobs.
 * Behaviour is preserved (value, range, unit, primary/secondary tier); only the
 * visual affordance differs.
 */
export function StudioPluginDock({ chain, onChange, trackName }: Props) {
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [query, setQuery] = useState("");

  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return STUDIO_PLUGINS;
    return STUDIO_PLUGINS.filter(
      (plugin) =>
        plugin.name.toLowerCase().includes(needle) ||
        plugin.description.toLowerCase().includes(needle)
    );
  }, [query]);

  function add(pluginId: PluginId) {
    onChange(addPlugin(chain, pluginId));
    setCatalogOpen(false);
    setQuery("");
  }

  return (
    <section className="sp-dock" aria-label={trackName ? `Plugins for ${trackName}` : "Plugin chain"}>
      <div className="sp-rail">
        {chain.length === 0 ? (
          <div className="sp-empty">
            <p>No effects on this track yet.</p>
            <button type="button" className="sp-add-inline" onClick={() => setCatalogOpen(true)}>
              <Icon name="fa-plus" /> Add effect
            </button>
          </div>
        ) : null}

        {chain.map((entry, index) => {
          const plugin = getPlugin(entry.pluginId);
          if (!plugin) return null;
          const primary = plugin.params.filter((param) => param.tier !== "secondary");
          const secondary = plugin.params.filter((param) => param.tier === "secondary");
          return (
            <article
              key={entry.entryId}
              className={`sp-slot${entry.bypassed ? " is-bypassed" : ""}`}
              aria-label={`${plugin.name} slot ${index + 1}`}
            >
              <header className="sp-slot-head">
                <span className="sp-dot" aria-hidden="true" />
                <strong>{plugin.name}</strong>
                <button
                  type="button"
                  className="sp-preset"
                  onClick={() => onChange(commitPreset(chain, entry.entryId))}
                  title={entry.dirty ? "Save changes to this preset" : entry.presetName}
                >
                  {entry.dirty ? "Custom" : entry.presetName}
                </button>
                {entry.dirty ? (
                  <button
                    type="button"
                    className="sp-update"
                    onClick={() => onChange(commitPreset(chain, entry.entryId))}
                  >
                    Update
                  </button>
                ) : null}
                <button
                  type="button"
                  className={`sp-bypass${entry.bypassed ? " off" : ""}`}
                  aria-label={`Bypass ${plugin.name}`}
                  aria-pressed={entry.bypassed}
                  title={entry.bypassed ? "Bypassed" : "Active"}
                  onClick={() => onChange(toggleBypass(chain, entry.entryId))}
                />
                <span className="sp-slot-tools">
                  <button
                    type="button"
                    aria-label={`Move ${plugin.name} left`}
                    disabled={index === 0}
                    onClick={() => onChange(movePlugin(chain, entry.entryId, index - 1))}
                  >
                    <Icon name="fa-chevron-left" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Move ${plugin.name} right`}
                    disabled={index === chain.length - 1}
                    onClick={() => onChange(movePlugin(chain, entry.entryId, index + 1))}
                  >
                    <Icon name="fa-chevron-right" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Pop out ${plugin.name}`}
                    aria-pressed={entry.poppedOut}
                    onClick={() => onChange(togglePoppedOut(chain, entry.entryId))}
                  >
                    <Icon name="fa-up-right-from-square" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Remove ${plugin.name}`}
                    onClick={() => onChange(removePlugin(chain, entry.entryId))}
                  >
                    <Icon name="fa-xmark" />
                  </button>
                </span>
              </header>

              {plugin.modes?.length ? (
                <div className="sp-modes" role="tablist" aria-label={`${plugin.name} mode`}>
                  {plugin.modes.map((mode) => (
                    <button
                      key={mode.id}
                      type="button"
                      role="tab"
                      aria-selected={entry.mode === mode.id}
                      className={entry.mode === mode.id ? "on" : ""}
                      onClick={() => onChange(setMode(chain, entry.entryId, mode.id))}
                    >
                      {mode.label}
                    </button>
                  ))}
                </div>
              ) : null}

              {plugin.assetSlot ? (
                <div className="sp-asset" aria-label={plugin.assetSlot.label}>
                  {entry.assetId ? entry.assetId : plugin.assetSlot.emptyLabel}
                </div>
              ) : null}

              <div className="sp-params">
                {primary.map((param) => (
                  <ParamControl
                    key={param.key}
                    label={param.label}
                    unit={param.unit}
                    tier="primary"
                    min={param.min}
                    max={param.max}
                    value={entry.params[param.key] ?? param.default}
                    disabled={entry.bypassed}
                    onChange={(value) => onChange(setParam(chain, entry.entryId, param.key, value))}
                  />
                ))}
                {secondary.map((param) => (
                  <ParamControl
                    key={param.key}
                    label={param.label}
                    unit={param.unit}
                    tier="secondary"
                    min={param.min}
                    max={param.max}
                    value={entry.params[param.key] ?? param.default}
                    disabled={entry.bypassed}
                    onChange={(value) => onChange(setParam(chain, entry.entryId, param.key, value))}
                  />
                ))}
              </div>
            </article>
          );
        })}

        <button type="button" className="sp-add" onClick={() => setCatalogOpen(true)}>
          <Icon name="fa-plus" /> Add effect
        </button>
      </div>

      {catalogOpen ? (
        <div className="sp-dialog-backdrop" role="presentation" onClick={() => setCatalogOpen(false)}>
          <div
            className="sp-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="sp-catalog-title"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="sp-dialog-head">
              <h2 id="sp-catalog-title">Add a track plugin</h2>
              <label className="sp-search">
                <Icon name="fa-magnifying-glass" />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search plugins"
                  aria-label="Search plugins"
                  autoFocus
                />
              </label>
              <button
                type="button"
                className="sp-dialog-close"
                aria-label="Close"
                onClick={() => setCatalogOpen(false)}
              >
                <Icon name="fa-xmark" />
              </button>
            </header>

            <div className="sp-catalog">
              {results.map((plugin) => (
                <button
                  key={plugin.id}
                  type="button"
                  className="sp-card"
                  onClick={() => add(plugin.id)}
                >
                  <span className="sp-card-name">
                    {plugin.name}
                    {plugin.unverified ? <em title="Not yet confirmed against the reference">unverified</em> : null}
                  </span>
                  <span className="sp-card-desc">{plugin.description}</span>
                </button>
              ))}
              {results.length === 0 ? (
                <p className="sp-none">No effects match “{query}”.</p>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function ParamControl({
  label,
  unit,
  tier,
  min,
  max,
  value,
  disabled,
  onChange,
}: {
  label: string;
  unit?: string;
  tier: "primary" | "secondary";
  min: number;
  max: number;
  value: number;
  disabled?: boolean;
  onChange: (value: number) => void;
}) {
  const step = max - min > 100 ? 1 : 0.01;
  const display =
    unit === "hz" && value >= 1000
      ? `${(value / 1000).toFixed(1)}k`
      : Number.isInteger(value)
        ? String(value)
        : value.toFixed(2);
  return (
    <label className={`sp-param ${tier}`}>
      <span className="sp-param-label">{label}</span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
        aria-label={label}
      />
      <span className="sp-param-value">
        {display}
        {unit && unit !== "%" ? unit : unit === "%" ? "%" : ""}
      </span>
    </label>
  );
}
