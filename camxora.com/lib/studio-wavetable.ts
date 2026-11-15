/**
 * Wavetable Designer (reference §30 N-14; gated by Content → Advanced content features).
 *
 * A designed wavetable is a set of sine-partial amplitudes. The MIDI synth turns it into
 * a `PeriodicWave` with `createPeriodicWave`, so a designed table is a real instrument
 * voice, not a label. Tables live in the project document (`data.wavetables`) so they
 * travel with the arrangement and follow the same save/undo path as everything else.
 */

export type CustomWavetable = {
  id: string;
  name: string;
  /** Sine-partial amplitudes, fundamental first. 16 partials matches the designer UI. */
  harmonics: number[];
};

export const WAVETABLE_PARTIALS = 16;

export type WavetablePreset = { id: string; name: string; harmonics: number[] };

/** Starter shapes (all normalised; a saw is 1/n, a square is the odd harmonics). */
export const WAVETABLE_PRESETS: WavetablePreset[] = [
  {
    id: "saw",
    name: "Saw",
    harmonics: Array.from({ length: WAVETABLE_PARTIALS }, (_, index) => 1 / (index + 1)),
  },
  {
    id: "square",
    name: "Square",
    harmonics: Array.from({ length: WAVETABLE_PARTIALS }, (_, index) =>
      index % 2 === 0 ? 1 / (index + 1) : 0
    ),
  },
  {
    id: "triangle",
    name: "Triangle",
    harmonics: Array.from({ length: WAVETABLE_PARTIALS }, (_, index) =>
      index % 2 === 0 ? 1 / (index + 1) ** 2 : 0
    ),
  },
  {
    id: "organ",
    name: "Organ",
    harmonics: [1, 0, 0.6, 0, 0.35, 0, 0.2, 0, 0.12, 0, 0, 0, 0, 0, 0, 0],
  },
  {
    id: "hollow",
    name: "Hollow",
    harmonics: Array.from({ length: WAVETABLE_PARTIALS }, (_, index) =>
      index % 3 === 0 ? 1 / (index / 3 + 1) : 0
    ),
  },
];

export function sanitizeHarmonics(input: unknown): number[] {
  const source = Array.isArray(input) ? input : [];
  return Array.from({ length: WAVETABLE_PARTIALS }, (_, index) => {
    const value = Number(source[index] ?? 0);
    return Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;
  });
}

/** Read `data.wavetables`, falling back to an empty list instead of throwing. */
export function sanitizeWavetables(input: unknown): CustomWavetable[] {
  if (!Array.isArray(input)) return [];
  const seen = new Set<string>();
  const next: CustomWavetable[] = [];
  for (const candidate of input) {
    if (!candidate || typeof candidate !== "object") continue;
    const row = candidate as { id?: unknown; name?: unknown; harmonics?: unknown };
    const id = typeof row.id === "string" ? row.id.trim() : "";
    if (!id || seen.has(id)) continue;
    seen.add(id);
    next.push({
      id,
      name: typeof row.name === "string" && row.name.trim() ? row.name.trim().slice(0, 40) : "Wavetable",
      harmonics: sanitizeHarmonics(row.harmonics),
    });
    if (next.length >= 32) break;
  }
  return next;
}

/** A stable id for a new design; the name is not unique, the id is. */
export function nextWavetableId(): string {
  return `wt-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

/** `wavetable:<id>` is the instrument id a MIDI clip stores. */
export function wavetableInstrumentId(id: string): string {
  return `wavetable:${id}`;
}

export function wavetableIdFromInstrument(instrument: string | undefined | null): string | null {
  if (typeof instrument !== "string" || !instrument.startsWith("wavetable:")) return null;
  const id = instrument.slice("wavetable:".length).trim();
  return id || null;
}

/** Build the periodic wave for a design, for playback and the designer's preview. */
export function wavetablePeriodicWave(
  context: BaseAudioContext,
  harmonics: number[]
): PeriodicWave {
  const real = new Float32Array(harmonics.length + 1);
  const imag = new Float32Array(harmonics.length + 1);
  harmonics.forEach((amplitude, index) => {
    imag[index + 1] = amplitude;
  });
  return context.createPeriodicWave(real, imag, { disableNormalization: false });
}

/** One cycle of the design, for drawing it without an AudioContext. */
export function wavetableSamples(harmonics: number[], count = 256): number[] {
  const samples: number[] = [];
  for (let index = 0; index < count; index += 1) {
    const phase = (index / count) * Math.PI * 2;
    let value = 0;
    harmonics.forEach((amplitude, partial) => {
      value += amplitude * Math.sin(phase * (partial + 1));
    });
    samples.push(value);
  }
  const peak = Math.max(1e-6, ...samples.map((value) => Math.abs(value)));
  return samples.map((value) => value / peak);
}
