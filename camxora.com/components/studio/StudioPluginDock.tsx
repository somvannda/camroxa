"use client";

import { useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

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

const EQ_F_MIN = 20;
const EQ_F_MAX = 20000;
const EQ_DB = 24;
const EQ_W = 400;
const EQ_H = 124;
const EQ_PAD = 8;
const EQ_TYPES = ["highpass", "peaking", "highshelf", "lowshelf", "lowpass", "notch"] as const;

/** Filter shapes from the captured card (S42), drawn as tiny curve glyphs. */
const EQ_SHAPES: Array<{ id: number; label: string; path: string }> = [
  { id: 0, label: "Low cut", path: "M1 8 H12 Q16 8 19 14 L27 16" },
  { id: 1, label: "Bell", path: "M1 15 Q7 15 10 9 Q13 3 16 9 Q19 15 27 15" },
  { id: 2, label: "High shelf", path: "M1 15 H9 Q13 15 16 8 H27" },
  { id: 3, label: "Low shelf", path: "M1 8 H12 Q15 15 19 15 H27" },
  { id: 4, label: "High cut", path: "M1 2 Q9 2 12 8 Q15 14 18 16 H27" },
  { id: 5, label: "Notch", path: "M1 8 H10 L13 15 L16 8 H27" },
];

/** One band's magnitude in dB at a frequency (display curve, not the DSP filter). */
function bandDb(freq: number, band: { freq: number; q: number; gain: number; type: number; on: boolean }) {
  if (!band.on) return 0;
  const octaves = Math.log2(freq / Math.max(1, band.freq));
  const width = Math.max(0.35, 2.2 / Math.max(0.1, band.q));
  switch (band.type) {
    case 0:
      return -24 / (1 + Math.pow(freq / band.freq, 6));
    case 2:
      return band.gain * (1 - 1 / (1 + Math.pow(freq / band.freq, 6)));
    case 3:
      return band.gain / (1 + Math.pow(freq / band.freq, 6));
    case 4:
      return -24 / (1 + Math.pow(band.freq / Math.max(1, freq), 6));
    case 5:
      return -Math.abs(band.gain || 18) * Math.exp(-Math.pow(octaves / 0.18, 2));
    default:
      return band.gain * Math.exp(-Math.pow(octaves / width, 2));
  }
}

function formatFreq(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}khz`;
  return `${Math.round(value)}hz`;
}

function Knob({
  label,
  value,
  min,
  max,
  step,
  title,
  log,
  disabled,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  title: string;
  log?: boolean;
  disabled?: boolean;
  onChange: (value: number) => void;
}) {
  const pct = log
    ? Math.min(
        1,
        Math.max(
          0,
          (Math.log(Math.max(1, value)) - Math.log(min)) / (Math.log(max) - Math.log(min))
        )
      )
    : Math.min(1, Math.max(0, (value - min) / (max - min)));
  return (
    <label className="sp-knob">
      <span
        className="sp-knob-dial"
        style={{ ["--p" as string]: `${(pct * 270).toFixed(1)}deg` }}
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
        step={step}
        value={value}
        aria-label={label}
        aria-valuetext={title}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <span className="sp-knob-label">{label}</span>
    </label>
  );
}

/**
 * EQ card from the dock capture (S40/S42): band selector with an enable switch, the six
 * filter-shape buttons, a shared curve with one handle per band, and three knobs for the
 * selected band. The model carries four bands (see studio-plugins); the curve is display
 * math over the same params the audio chain uses.
 */
function EqCard({
  params,
  disabled,
  onChange,
}: {
  params: Record<string, number>;
  disabled: boolean;
  onChange: (key: string, value: number) => void;
}) {
  const [selected, setSelected] = useState(1);
  const [dragging, setDragging] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  const value = (key: string, fallback: number) => params[key] ?? fallback;
  const bands = [1, 2, 3, 4].map((n) => ({
    n,
    freq: value(`band${n}.freq`, n === 1 ? 1000 : n === 2 ? 200 : n === 3 ? 4000 : 10000),
    q: value(`band${n}.q`, 1),
    gain: value(`band${n}.gain`, 0),
    type: Math.round(value(`band${n}.type`, 1)),
    on: value(`band${n}.on`, 1) >= 0.5,
  }));
  const current = bands[selected - 1];

  const xFor = (freq: number) => {
    const t =
      (Math.log10(Math.max(EQ_F_MIN, freq)) - Math.log10(EQ_F_MIN)) /
      (Math.log10(EQ_F_MAX) - Math.log10(EQ_F_MIN));
    return EQ_PAD + Math.min(1, Math.max(0, t)) * (EQ_W - EQ_PAD * 2);
  };
  const yFor = (db: number) => EQ_H / 2 - (db / EQ_DB) * (EQ_H / 2 - EQ_PAD);

  const points: string[] = [];
  for (let px = EQ_PAD; px <= EQ_W - EQ_PAD; px += 3) {
    const t = (px - EQ_PAD) / (EQ_W - EQ_PAD * 2);
    const freq = Math.pow(10, Math.log10(EQ_F_MIN) + t * (Math.log10(EQ_F_MAX) - Math.log10(EQ_F_MIN)));
    const db = bands.reduce((sum, band) => sum + bandDb(freq, band), 0);
    points.push(`${px.toFixed(1)},${yFor(Math.max(-EQ_DB, Math.min(EQ_DB, db))).toFixed(1)}`);
  }
  const curve = `M ${EQ_PAD},${EQ_H / 2} L ${points.join(" L ")} L ${EQ_W - EQ_PAD},${EQ_H / 2}`;

  const dragTo = (clientX: number, clientY: number, band: number) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const tx = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    const ty = Math.min(1, Math.max(0, (clientY - rect.top) / rect.height));
    const freq = Math.round(EQ_F_MIN * Math.pow(EQ_F_MAX / EQ_F_MIN, tx));
    const gain = Math.round((0.5 - ty) * 2 * EQ_DB * 10) / 10;
    onChange(`band${band}.freq`, Math.min(EQ_F_MAX, Math.max(EQ_F_MIN, freq)));
    onChange(`band${band}.gain`, Math.min(EQ_DB, Math.max(-EQ_DB, gain)));
  };

  return (
    <div className="sp-eq-card">
      <div className="sp-eq-bandbar">
        <select
          className="sp-band-select"
          aria-label="EQ band"
          value={selected}
          disabled={disabled}
          onChange={(event) => setSelected(Number(event.target.value))}
        >
          {bands.map((band) => (
            <option key={band.n} value={band.n}>
              Band {band.n}
            </option>
          ))}
        </select>
        <button
          type="button"
          role="switch"
          aria-checked={current.on}
          aria-label={`Band ${selected} enabled`}
          disabled={disabled}
          className={`sp-band-toggle${current.on ? " on" : ""}`}
          onClick={() => onChange(`band${selected}.on`, current.on ? 0 : 1)}
        />
      </div>

      <div className="sp-eq-shapes" role="group" aria-label="Filter shape">
        {EQ_SHAPES.map((shape) => (
          <button
            key={shape.id}
            type="button"
            aria-label={shape.label}
            aria-pressed={current.type === shape.id}
            disabled={disabled}
            className={current.type === shape.id ? "on" : undefined}
            onClick={() => onChange(`band${selected}.type`, shape.id)}
          >
            <svg viewBox="0 0 28 18" aria-hidden="true">
              <path d={shape.path} />
            </svg>
          </button>
        ))}
      </div>

      <svg
        className="sp-eq"
        viewBox={`0 0 ${EQ_W} ${EQ_H}`}
        role="img"
        ref={svgRef}
        aria-label="EQ curve: drag a band handle to set frequency and gain"
        onPointerMove={(event) => {
          if (dragging === null) return;
          if (event.buttons !== 1) {
            setDragging(null);
            return;
          }
          dragTo(event.clientX, event.clientY, dragging);
        }}
        onPointerUp={() => setDragging(null)}
        onPointerCancel={() => setDragging(null)}
        onPointerLeave={() => setDragging(null)}
      >
        <line x1={EQ_PAD} x2={EQ_W - EQ_PAD} y1={EQ_H / 2} y2={EQ_H / 2} className="sp-eq-axis" />
        {[100, 1000, 10000].map((freq) => (
          <line
            key={freq}
            x1={xFor(freq)}
            x2={xFor(freq)}
            y1={EQ_PAD}
            y2={EQ_H - EQ_PAD}
            className="sp-eq-grid"
          />
        ))}
        <path d={`${curve} Z`} className="sp-eq-fill" />
        <path d={curve} className="sp-eq-line" />
        {bands.map((band) =>
          band.on ? (
            <circle
              key={band.n}
              cx={xFor(band.freq)}
              cy={yFor(Math.max(-EQ_DB, Math.min(EQ_DB, bandDb(band.freq, band))))}
              r={selected === band.n ? 5 : 4}
              className={`sp-eq-handle${selected === band.n ? " on" : ""}`}
              role="button"
              aria-label={`Band ${band.n} handle`}
              onPointerDown={(event) => {
                setSelected(band.n);
                setDragging(band.n);
                dragTo(event.clientX, event.clientY, band.n);
              }}
            />
          ) : null
        )}
      </svg>

      <div className="sp-knobs">
        <Knob
          label="Freq"
          value={current.freq}
          min={EQ_F_MIN}
          max={EQ_F_MAX}
          step={1}
          title={formatFreq(current.freq)}
          log
          disabled={disabled}
          onChange={(next) => onChange(`band${selected}.freq`, next)}
        />
        <Knob
          label="Q"
          value={current.q}
          min={0.1}
          max={18}
          step={0.1}
          title={current.q.toFixed(1)}
          disabled={disabled}
          onChange={(next) => onChange(`band${selected}.q`, next)}
        />
        <Knob
          label="Gain"
          value={current.gain}
          min={-24}
          max={24}
          step={0.5}
          title={`${current.gain}db`}
          disabled={disabled}
          onChange={(next) => onChange(`band${selected}.gain`, next)}
        />
      </div>
    </div>
  );
}

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
              className={`sp-slot${entry.bypassed ? " is-bypassed" : ""}${
                plugin.id === "eq" ? " sp-slot-eq" : ""
              }`}
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

              {plugin.id === "eq" ? (
                <EqCard
                  params={entry.params}
                  disabled={Boolean(entry.bypassed)}
                  onChange={(key, value) => onChange(setParam(chain, entry.entryId, key, value))}
                />
              ) : (
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
              )}
            </article>
          );
        })}

        {chain.length > 0 ? (
          <button type="button" className="sp-add" onClick={() => setCatalogOpen(true)}>
            <Icon name="fa-plus" /> Add effect
          </button>
        ) : null}
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

            <p className="sp-catalog-label">Audio effects</p>
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
