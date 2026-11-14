"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";

import { Icon } from "@/components/Icon";
import { ParamKnob } from "@/components/studio/ParamKnob";
import {
  STUDIO_PLUGINS,
  customAsDef,
  customParamMap,
  defaultParams,
  getPlugin,
  makeUserPreset,
  presetsFor,
  userPresetsFor,
  type CustomPlugin,
  type ParamDef,
  type PluginChainEntry,
  type PluginDef,
  type PluginId,
  type UserPreset,
} from "@/lib/studio-plugins";
import {
  addCustomPlugin,
  addPlugin,
  applyPreset,
  commitPreset,
  movePlugin,
  removePlugin,
  setAsset,
  setMode,
  setSidechain,
  setParam,
  toggleBypass,
  togglePoppedOut,
} from "@/lib/studio-plugin-chain";
import {
  IMPULSE_CATEGORIES,
  customImpulseResponses,
  findImpulseResponse,
  impulseEnvelope,
  impulseLabel,
  type ImpulseResponse,
} from "@/lib/studio-ir";
import { StudioIRDesigner } from "@/components/studio/StudioIRDesigner";
import type { StudioWindowMode } from "@/lib/studio-settings";

type Props = {
  chain: PluginChainEntry[];
  onChange: (next: PluginChainEntry[]) => void;
  /** Track name, shown in the dock header. */
  trackName?: string;
  /** Designed plugins (S45) saved in this project's library. */
  customPlugins?: CustomPlugin[];
  /** Opens the prompt bar in design mode (S45 entry). */
  onDesignPlugin?: () => void;
  /** Tracks available as a compressor sidechain key (S43). */
  tracks?: Array<{ id: string; name: string }>;
  /** Presets saved from the card menu (S46 "Save preset…"). */
  userPresets?: UserPreset[];
  onSavePreset?: (
    pluginId: string,
    name: string,
    params: Record<string, number>,
    mode?: string
  ) => void;
  /** S10: whether cards open docked, floating, or with a per-card toggle. */
  windowMode?: StudioWindowMode;
  /** S11: sound-design tools are hidden when this is off. */
  advancedContent?: boolean;
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
const EQ_W = 240;
const EQ_H = 160;
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

/** Soft-knee compressor response drawn from the live params (S41). */
function CompressorCurve({ params }: { params: Record<string, number> }) {
  const threshold = params.threshold ?? -18;
  const ratio = Math.max(1, params.ratio ?? 4);
  const knee = Math.max(0, params.knee ?? 6);
  const width = 220;
  const height = 104;
  const pad = 10;
  const span = 60;
  const x = (db: number) => pad + ((db + span) / span) * (width - pad * 2);
  const y = (db: number) => height - pad - ((db + span) / span) * (height - pad * 2);
  const outDb = (input: number) => {
    const over = input - threshold;
    if (knee <= 0) return over > 0 ? threshold + over / ratio : input;
    const half = knee / 2;
    if (over <= -half) return input;
    if (over >= half) return threshold + over / ratio;
    const t = over + half;
    return input + ((1 / ratio - 1) * t * t) / (2 * knee);
  };
  const samples = Array.from({ length: 61 }, (_, index) => -span + (index / 60) * span);
  const curve = samples
    .map((db, index) => `${index === 0 ? "M" : "L"}${x(db).toFixed(1)} ${y(Math.max(-span, outDb(db))).toFixed(1)}`)
    .join(" ");
  return (
    <svg
      className="sp-comp-curve"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="Compressor transfer curve"
    >
      <line
        x1={x(-span)}
        y1={y(-span)}
        x2={x(0)}
        y2={y(0)}
        className="sp-comp-axis"
        strokeDasharray="3 4"
      />
      <path d={curve} className="sp-comp-line" />
      <circle cx={x(threshold)} cy={y(outDb(threshold))} r={4} className="sp-comp-dot" />
      <text x={pad} y={height - 1} className="sp-comp-label">
        -60
      </text>
      <text x={width - pad - 10} y={height - 1} className="sp-comp-label">
        0
      </text>
    </svg>
  );
}

/** Convolution card (S44): impulse slot + grouped IR picker, then Mix/Gain/Pre/Width. */
function ConvolutionCard({
  assetId,
  params,
  values,
  disabled,
  onAsset,
  onChange,
  advancedContent,
}: {
  assetId: string | null;
  params: ParamDef[];
  values: Record<string, number>;
  disabled: boolean;
  onAsset: (id: string | null) => void;
  onChange: (key: string, value: number) => void;
  advancedContent: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState<string | null>(null);
  const [menuBox, setMenuBox] = useState<{ left: number; top: number } | null>(null);
  const [custom, setCustom] = useState<ImpulseResponse[]>(() => customImpulseResponses());
  const [designOpen, setDesignOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const response = custom.find((item) => item.id === assetId) ?? findImpulseResponse(assetId);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const envelope = response ? impulseEnvelope(response) : [];
  const width = 260;
  const height = 64;
  const points = envelope.map(
    (value, index) =>
      [
        (index / Math.max(1, envelope.length - 1)) * width,
        height / 2 - value * (height / 2 - 4),
      ] as const
  );
  const wave = points.length
    ? `M${points.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(" L")} L${points
        .slice()
        .reverse()
        .map(([x, y]) => `${x.toFixed(1)} ${(height - y).toFixed(1)}`)
        .join(" L")} Z`
    : "";

  return (
    <>
    <div className="sp-conv-body">
      <div className="sp-conv-slot">
        <svg
          className="sp-ir"
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={response ? `Impulse response ${response.name}` : "No impulse response"}
        >
          <line x1={0} x2={width} y1={height / 2} y2={height / 2} className="sp-ir-axis" />
          {[0, 1, 2, 3].map((second) => {
            const x = (second / 3) * width;
            return (
              <g key={second}>
                <line
                  x1={x}
                  x2={x}
                  y1={0}
                  y2={height}
                  className="sp-ir-tick"
                  aria-hidden="true"
                />
                <text x={Math.min(x + 4, width - 20)} y={height - 3} className="sp-ir-label">
                  {second}s
                </text>
              </g>
            );
          })}
          {wave ? <path d={wave} className="sp-ir-wave" /> : null}
          <circle cx={width - 12} cy={12} r={6} className="sp-ir-dot" />
        </svg>
        <div className="sp-ir-picker" ref={wrapRef}>
          <button
            type="button"
            aria-haspopup="menu"
            aria-expanded={open}
            aria-label="Impulse response"
            disabled={disabled}
            onClick={(event) => {
              if (!open) {
                const rect = event.currentTarget.getBoundingClientRect();
                setMenuBox({ left: rect.left, top: Math.max(8, rect.top - 268) });
              }
              setOpen((value) => !value);
            }}
          >
            <span>{response ? impulseLabel(assetId) : "No impulse response"}</span>
            <Icon name="fa-chevron-down" />
          </button>
          {open ? (
            <div
              className="sp-ir-menu"
              role="menu"
              aria-label="Impulse responses"
              style={menuBox ? { left: menuBox.left, top: menuBox.top } : undefined}
            >
              {IMPULSE_CATEGORIES.map((group) => (
                <div key={group.label}>
                  <button
                    type="button"
                    role="menuitem"
                    className="sp-ir-cat"
                    aria-expanded={category === group.label}
                    onClick={() =>
                      setCategory((current) => (current === group.label ? null : group.label))
                    }
                  >
                    {group.label}
                  </button>
                  {category === group.label
                    ? group.items.map((ir) => (
                        <button
                          key={ir.id}
                          type="button"
                          role="menuitem"
                          className={assetId === ir.id ? "on" : undefined}
                          onClick={() => {
                            onAsset(ir.id);
                            setOpen(false);
                          }}
                        >
                          {ir.name}
                        </button>
                      ))
                    : null}
                </div>
              ))}
              {custom.length > 0 ? (
                <div>
                  <button
                    type="button"
                    role="menuitem"
                    className="sp-ir-cat"
                    aria-expanded={category === "Custom"}
                    onClick={() =>
                      setCategory((current) => (current === "Custom" ? null : "Custom"))
                    }
                  >
                    Custom
                  </button>
                  {category === "Custom"
                    ? custom.map((ir) => (
                        <button
                          key={ir.id}
                          type="button"
                          role="menuitem"
                          className={assetId === ir.id ? "on" : undefined}
                          onClick={() => {
                            onAsset(ir.id);
                            setOpen(false);
                          }}
                        >
                          {ir.name}
                        </button>
                      ))
                    : null}
                </div>
              ) : null}
              {advancedContent ? (
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setOpen(false);
                    setDesignOpen(true);
                  }}
                >
                  <Icon name="fa-plus" /> Design response.
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
      <div className="sp-knobs sp-knob-grid">
        {params.map((param) =>
          param.choices ? (
            <label key={param.key} className="sp-knob">
              <select
                className="sp-choice"
                aria-label={param.label}
                value={values[param.key] ?? param.default}
                disabled={disabled}
                onChange={(event) => onChange(param.key, Number(event.target.value))}
              >
                {param.choices.map((choice) => (
                  <option key={choice.value} value={choice.value}>
                    {choice.label}
                  </option>
                ))}
              </select>
              <span className="sp-knob-label">{param.label}</span>
            </label>
          ) : (
            <ParamKnob
              key={param.key}
              label={param.label}
              unit={param.unit}
              min={param.min}
              max={param.max}
              step={param.max - param.min > 100 ? 1 : 0.1}
              value={values[param.key] ?? param.default}
              disabled={disabled}
              onChange={(value) => onChange(param.key, value)}
            />
          )
        )}
      </div>
    </div>
    {designOpen ? (
      <StudioIRDesigner
        onSave={(saved) => {
          setCustom(customImpulseResponses());
          onAsset(saved.id);
          setDesignOpen(false);
        }}
        onClose={() => setDesignOpen(false)}
      />
    ) : null}
    </>
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
        <ParamKnob
          label="Freq"
          value={current.freq}
          min={EQ_F_MIN}
          max={EQ_F_MAX}
          step={1}
          unit="hz"
          log
          disabled={disabled}
          onChange={(next) => onChange(`band${selected}.freq`, next)}
        />
        <ParamKnob
          label="Q"
          value={current.q}
          min={0.1}
          max={18}
          step={0.1}
          disabled={disabled}
          onChange={(next) => onChange(`band${selected}.q`, next)}
        />
        <ParamKnob
          label="Gain"
          value={current.gain}
          min={-24}
          max={24}
          step={0.5}
          unit="db"
          disabled={disabled}
          onChange={(next) => onChange(`band${selected}.gain`, next)}
        />
      </div>
    </div>
  );
}


/** Small device preview on each catalog card (S39): knobs plus a family-shaped trace. */
const PREVIEW_PATHS: Record<string, string> = {
  eq: "M0 30 H30 Q55 30 70 14 Q85 -2 100 14 Q115 30 140 30 H200",
  compressor: "M0 40 L60 30 L120 16 L200 10",
  limiter: "M0 26 L120 20 L150 12 L200 12",
  gate: "M0 8 H70 L80 46 H200",
  delay: "M0 30 H40 L50 12 L60 30 H80 L90 18 L100 30 H120 L130 22 L140 30 H200",
  reverb: "M0 12 Q40 12 60 30 Q90 52 200 44",
  rhythmGate: "M0 10 H30 V44 H50 V10 H80 V44 H100 V10 H130 V44 H150 V10 H180 V44 H200",
  distortion: "M0 42 L20 18 L40 42 L60 18 L80 42 L100 18 L120 42 L140 18 L160 42 L180 18 L200 42",
  convolution: "M0 46 L30 44 L60 10 L70 40 L90 34 L120 42 L150 40 L200 46",
};

function PluginPreview({ id }: { id: string }) {
  const path = PREVIEW_PATHS[id] ?? "M0 30 H200";
  return (
    <span className="sp-card-preview" aria-hidden="true">
      <svg viewBox="0 0 200 52" preserveAspectRatio="none">
        <path d={path} />
      </svg>
      <span className="sp-card-knobs">
        {[0.32, 0.55, 0.74].map((value, index) => (
          <span
            key={index}
            className="sp-card-knob"
            style={{ ["--p" as string]: `${(value * 270).toFixed(0)}deg` }}
          />
        ))}
      </span>
    </span>
  );
}

export function StudioPluginDock({
  chain,
  onChange,
  trackName,
  customPlugins = [],
  onDesignPlugin,
  tracks = [],
  userPresets = [],
  onSavePreset,
  windowMode = "toggle",
  advancedContent = false,
}: Props) {
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [presetMenu, setPresetMenu] = useState<string | null>(null);
  const [savePresetFor, setSavePresetFor] = useState<string | null>(null);
  const [savePresetName, setSavePresetName] = useState("");
  const [sidechainMenu, setSidechainMenu] = useState<{ id: string; left: number; top: number } | null>(
    null
  );

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

  function addDesigned(custom: CustomPlugin) {
    onChange(addCustomPlugin(chain, custom));
    setCatalogOpen(false);
    setQuery("");
  }

  const filteredCustom = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return customPlugins;
    return customPlugins.filter(
      (plugin) =>
        plugin.name.toLowerCase().includes(needle) ||
        plugin.description.toLowerCase().includes(needle)
    );
  }, [customPlugins, query]);

  /**
   * S10 Window management: "Panels" docks every card, "Windows" floats them all, and
   * "Show toggle" leaves the decision to each card's Pop out control (remembered in the
   * chain, so it survives a reload).
   */
  /**
   * S46: the `‹ Default ›` stepper auditions presets without opening the menu. It walks
   * the same list the menu shows (Default, starter presets, saved presets).
   */
  function stepPreset(
    entry: PluginChainEntry,
    plugin: PluginDef,
    direction: -1 | 1
  ) {
    const builtIn = presetsFor(plugin.id).map((preset) => ({
      id: preset.id as string | null,
      name: preset.name,
      params: preset.params,
      mode: preset.mode,
    }));
    const saved = userPresetsFor(userPresets, plugin.id).map((preset) => ({
      id: preset.id as string | null,
      name: preset.name,
      params: preset.params,
      mode: preset.mode,
    }));
    const list = [
      {
        id: null as string | null,
        name: "Default",
        params: defaultParams(plugin.id),
        mode: undefined as string | undefined,
      },
      ...builtIn,
      ...saved,
    ];
    const current = list.findIndex((preset) => preset.id === entry.presetId);
    const index =
      current === -1
        ? direction > 0
          ? 0
          : list.length - 1
        : (current + direction + list.length) % list.length;
    onChange(applyPreset(chain, entry.entryId, list[index]));
  }

  const isPopped = (entry: PluginChainEntry): boolean =>
    windowMode === "windows" ? true : windowMode === "panels" ? false : Boolean(entry.poppedOut);

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
          const plugin = entry.custom ? customAsDef(entry.custom) : getPlugin(entry.pluginId);
          if (!plugin) return null;
          const isDesigned = Boolean(entry.custom);
          const primary = plugin.params.filter((param) => param.tier !== "secondary");
          const secondary = plugin.params.filter((param) => param.tier === "secondary");
          return (
            <article
              key={entry.entryId}
              className={`sp-slot${entry.bypassed ? " is-bypassed" : ""}${
                plugin.id === "eq" ? " sp-slot-eq" : ""
              }${isPopped(entry) ? " is-popped" : ""}`}
              aria-label={`${plugin.name} slot ${index + 1}`}
            >
              <header className="sp-slot-head">
                <span className="sp-dot" aria-hidden="true" />
                <strong>{plugin.name}</strong>
                <span className="sp-preset-wrap">
                  {!isDesigned ? (
                    <button
                      type="button"
                      className="sp-preset-step"
                      aria-label={`Previous ${plugin.name} preset`}
                      onClick={() => stepPreset(entry, plugin, -1)}
                    >
                      <Icon name="fa-chevron-left" />
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="sp-preset"
                    aria-haspopup="menu"
                    aria-expanded={presetMenu === entry.entryId}
                    title="Presets"
                    disabled={isDesigned}
                    onClick={() =>
                      setPresetMenu((current) =>
                        current === entry.entryId ? null : entry.entryId
                      )
                    }
                  >
                    {entry.dirty ? "Custom" : entry.presetName}
                  </button>
                  {!isDesigned ? (
                    <button
                      type="button"
                      className="sp-preset-step"
                      aria-label={`Next ${plugin.name} preset`}
                      onClick={() => stepPreset(entry, plugin, 1)}
                    >
                      <Icon name="fa-chevron-right" />
                    </button>
                  ) : null}
                  {presetMenu === entry.entryId ? (
                    <div
                      className="sp-preset-menu"
                      role="menu"
                      aria-label={`${plugin.name} presets`}
                    >
                      <button
                        type="button"
                        role="menuitem"
                        className="danger"
                        onClick={() => {
                          onChange(
                            applyPreset(chain, entry.entryId, {
                              id: null,
                              name: "Custom",
                              params: entry.custom
                                ? { ...entry.custom.defaults }
                                : defaultParams(plugin.id as PluginId),
                            })
                          );
                          setPresetMenu(null);
                        }}
                      >
                        Clear all settings
                      </button>
                      <button
                        type="button"
                        role="menuitem"
                        disabled={!onSavePreset}
                        onClick={() => {
                          setSavePresetFor(entry.entryId);
                          setSavePresetName("");
                        }}
                      >
                        Save preset…
                      </button>
                      {savePresetFor === entry.entryId ? (
                        <div className="sp-preset-save">
                          <input
                            aria-label="Preset name"
                            value={savePresetName}
                            autoFocus
                            placeholder="Preset name"
                            onChange={(event) => setSavePresetName(event.target.value)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter") {
                                onSavePreset?.(
                                  plugin.id,
                                  savePresetName,
                                  entry.params,
                                  entry.mode
                                );
                                setSavePresetFor(null);
                                setSavePresetName("");
                                setPresetMenu(null);
                              }
                              if (event.key === "Escape") setSavePresetFor(null);
                            }}
                          />
                          <button
                            type="button"
                            onClick={() => {
                              onSavePreset?.(
                                plugin.id,
                                savePresetName,
                                entry.params,
                                entry.mode
                              );
                              setSavePresetFor(null);
                              setSavePresetName("");
                              setPresetMenu(null);
                            }}
                          >
                            Save
                          </button>
                        </div>
                      ) : null}
                      <button
                        type="button"
                        role="menuitem"
                        className={!entry.dirty && entry.presetName === "Default" ? "on" : undefined}
                        onClick={() => {
                          onChange(
                            applyPreset(chain, entry.entryId, {
                              id: null,
                              name: "Default",
                              params: entry.custom
                                ? { ...entry.custom.defaults }
                                : defaultParams(plugin.id as PluginId),
                            })
                          );
                          setPresetMenu(null);
                        }}
                      >
                        Default
                      </button>
                      {presetsFor(plugin.id).map((preset) => (
                        <button
                          key={preset.id}
                          type="button"
                          role="menuitem"
                          className={entry.presetId === preset.id ? "on" : undefined}
                          onClick={() => {
                            onChange(
                              applyPreset(chain, entry.entryId, {
                                id: preset.id,
                                name: preset.name,
                                params: preset.params,
                                mode: preset.mode,
                              })
                            );
                            setPresetMenu(null);
                          }}
                        >
                          {preset.name}
                        </button>
                      ))}
                      {userPresetsFor(userPresets, plugin.id).map((preset) => (
                        <button
                          key={preset.id}
                          type="button"
                          role="menuitem"
                          className={entry.presetId === preset.id ? "on" : undefined}
                          onClick={() => {
                            onChange(
                              applyPreset(chain, entry.entryId, {
                                id: preset.id,
                                name: preset.name,
                                params: preset.params,
                                mode: preset.mode,
                              })
                            );
                            setPresetMenu(null);
                          }}
                        >
                          {preset.name}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </span>
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
                  {windowMode === "toggle" ? (
                    <button
                      type="button"
                      aria-label={`${isPopped(entry) ? "Dock" : "Pop out"} ${plugin.name}`}
                      aria-pressed={isPopped(entry)}
                      onClick={() => onChange(togglePoppedOut(chain, entry.entryId))}
                    >
                      <Icon name="fa-up-right-from-square" />
                    </button>
                  ) : null}
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

              {plugin.id === "eq" ? (
                <EqCard
                  params={entry.params}
                  disabled={Boolean(entry.bypassed)}
                  onChange={(key, value) => onChange(setParam(chain, entry.entryId, key, value))}
                />
              ) : plugin.id === "convolution" ? (
                <ConvolutionCard
                  assetId={entry.assetId ?? null}
                  params={plugin.params}
                  values={entry.params}
                  disabled={Boolean(entry.bypassed)}
                  advancedContent={advancedContent}
                  onAsset={(id) => onChange(setAsset(chain, entry.entryId, id))}
                  onChange={(key, value) => onChange(setParam(chain, entry.entryId, key, value))}
                />
              ) : (
                <div className={plugin.id === "compressor" ? "sp-comp-body" : undefined}>
                  {plugin.id === "compressor" ? <CompressorCurve params={entry.params} /> : null}
                  <div className="sp-knobs sp-knob-grid">
                    {[...primary, ...secondary].map((param) =>
                      param.choices ? (
                        <label key={param.key} className="sp-knob">
                          <select
                            className="sp-choice"
                            aria-label={param.label}
                            value={entry.params[param.key] ?? param.default}
                            disabled={entry.bypassed}
                            onChange={(event) =>
                              onChange(
                                setParam(chain, entry.entryId, param.key, Number(event.target.value))
                              )
                            }
                          >
                            {param.choices.map((choice) => (
                              <option key={choice.value} value={choice.value}>
                                {choice.label}
                              </option>
                            ))}
                          </select>
                          <span className="sp-knob-label">{param.label}</span>
                        </label>
                      ) : (
                        <ParamKnob
                          key={param.key}
                          label={param.label}
                          unit={param.unit}
                          min={param.min}
                          max={param.max}
                          step={param.max - param.min > 100 ? 1 : 0.1}
                          log={param.unit === "hz"}
                          value={entry.params[param.key] ?? param.default}
                          disabled={entry.bypassed}
                          onChange={(value) =>
                            onChange(setParam(chain, entry.entryId, param.key, value))
                          }
                        />
                      )
                    )}
                  </div>
                </div>
              )}
              {plugin.id === "compressor" ? (
                <div className="sp-sidechain">
                  <span>Sidechain</span>
                  <button
                    type="button"
                    aria-haspopup="menu"
                    aria-expanded={sidechainMenu?.id === entry.entryId}
                    aria-label="Sidechain"
                    disabled={Boolean(entry.bypassed)}
                    onClick={(event) => {
                      if (sidechainMenu?.id === entry.entryId) {
                        setSidechainMenu(null);
                        return;
                      }
                      const rect = event.currentTarget.getBoundingClientRect();
                      setSidechainMenu({
                        id: entry.entryId,
                        left: rect.left,
                        top: Math.max(8, rect.top - 320),
                      });
                    }}
                  >
                    <span>
                      {entry.sidechain
                        ? `${
                            tracks.find((track) => track.id === entry.sidechain?.trackId)?.name ??
                            "Track"
                          } — ${entry.sidechain.tap === "pre" ? "Pre-fx" : "Post-fader"}`
                        : "None"}
                    </span>
                    <Icon name="fa-chevron-down" />
                  </button>
                  {sidechainMenu?.id === entry.entryId ? (
                    <div
                      className="sp-sidechain-menu"
                      role="menu"
                      aria-label="Sidechain routing"
                      style={{ left: sidechainMenu.left, top: sidechainMenu.top }}
                    >
                      <button
                        type="button"
                        role="menuitem"
                        className={!entry.sidechain ? "on" : undefined}
                        onClick={() => {
                          onChange(setSidechain(chain, entry.entryId, null));
                          setSidechainMenu(null);
                        }}
                      >
                        None
                      </button>
                      {tracks.flatMap((track) => [
                        <button
                          key={`${track.id}:pre`}
                          type="button"
                          role="menuitem"
                          className={
                            entry.sidechain?.trackId === track.id && entry.sidechain.tap === "pre"
                              ? "on"
                              : undefined
                          }
                          onClick={() => {
                            onChange(
                              setSidechain(chain, entry.entryId, { trackId: track.id, tap: "pre" })
                            );
                            setSidechainMenu(null);
                          }}
                        >
                          {track.name} — Pre-fx
                        </button>,
                        <button
                          key={`${track.id}:post`}
                          type="button"
                          role="menuitem"
                          className={
                            entry.sidechain?.trackId === track.id && entry.sidechain.tap === "post"
                              ? "on"
                              : undefined
                          }
                          onClick={() => {
                            onChange(
                              setSidechain(chain, entry.entryId, { trackId: track.id, tap: "post" })
                            );
                            setSidechainMenu(null);
                          }}
                        >
                          {track.name} — Post-fader
                        </button>,
                      ])}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </article>
          );
        })}

        {chain.length > 0 ? (
          <div className="sp-empty-rail" aria-label="Add another effect">
            <button type="button" className="sp-add" onClick={() => setCatalogOpen(true)}>
              <Icon name="fa-plus" /> Add effect
            </button>
            <div className="sp-ghosts">
              {(["compressor", "reverb", "delay"] as PluginId[])
                .filter((id) => !chain.some((entry) => entry.pluginId === id))
                .slice(0, 3)
                .map((id) => {
                  const suggestion = getPlugin(id);
                  if (!suggestion) return null;
                  return (
                    <button
                      key={id}
                      type="button"
                      className="sp-ghost"
                      aria-label={`Add ${suggestion.name}`}
                      onClick={() => add(id)}
                    >
                      <PluginPreview id={id} />
                      <span className="sp-ghost-label">{suggestion.name}</span>
                    </button>
                  );
                })}
            </div>
          </div>
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

            <p className="sp-catalog-label">My plugins</p>
            <div className="sp-catalog sp-catalog-mine">
              <button
                type="button"
                className="sp-card sp-create"
                onClick={() => {
                  setCatalogOpen(false);
                  setQuery("");
                  onDesignPlugin?.();
                }}
              >
                <span className="sp-create-plus" aria-hidden="true">
                  <Icon name="fa-plus" />
                </span>
                <span className="sp-create-label">
                  Create new plugin
                  <span className="sp-card-badge">BETA</span>
                </span>
                <span className="sp-card-desc">Describe it in the prompt bar</span>
              </button>
              {filteredCustom.map((custom) => (
                <button
                  key={custom.id}
                  type="button"
                  className="sp-card sp-card-designed"
                  onClick={() => addDesigned(custom)}
                >
                  <span className="sp-designed-glyph" aria-hidden="true">
                    <Icon name="fa-wave-square" />
                  </span>
                  <span className="sp-card-name">{custom.name}</span>
                  <span className="sp-card-desc">{custom.description}</span>
                </button>
              ))}
            </div>

            <p className="sp-catalog-label">Audio effects</p>
            <div className="sp-catalog">
              {results.map((plugin) => (
                <button
                  key={plugin.id}
                  type="button"
                  className="sp-card"
                  onClick={() => add(plugin.id)}
                >
                  <PluginPreview id={plugin.id} />
                  <span className="sp-card-name">
                    {plugin.name}
                    <span
                      className="sp-card-learn"
                      data-help={`plugin-${plugin.id.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)}`}
                      onClick={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                      }}
                    >
                      <Icon name="fa-circle-play" /> Learn
                    </span>
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


