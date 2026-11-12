/**
 * Wavetable library for the custom MIDI synth.
 *
 * A table is a short harmonic series: the designer edits the first eight partials,
 * playback turns them into a `PeriodicWave`, and the same partials draw the preview.
 */

export type Wavetable = {
  id: string;
  name: string;
  /** Partial amplitudes 1..8, 0..1. */
  harmonics: number[];
};

const CUSTOM_KEY = "studio:wavetables";
const HARMONIC_COUNT = 8;
let customTables: Wavetable[] = [];
let loaded = false;

function normalizeHarmonics(input: unknown): number[] {
  const values = Array.isArray(input) ? input : [];
  return Array.from({ length: HARMONIC_COUNT }, (_, index) => {
    const value = Number(values[index]);
    return Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : index === 0 ? 1 : 0;
  });
}

function ensureLoaded(): void {
  if (loaded || typeof window === "undefined") return;
  loaded = true;
  try {
    const raw = window.localStorage.getItem(CUSTOM_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return;
    customTables = parsed
      .map((item) => {
        if (!item || typeof item !== "object") return null;
        const value = item as Record<string, unknown>;
        if (typeof value.id !== "string" || typeof value.name !== "string") return null;
        return {
          id: value.id,
          name: value.name.slice(0, 60),
          harmonics: normalizeHarmonics(value.harmonics),
        } satisfies Wavetable;
      })
      .filter((item): item is Wavetable => item !== null);
  } catch {
    /* private mode / corrupt blob */
  }
}

export function customWavetables(): Wavetable[] {
  ensureLoaded();
  return [...customTables];
}

export function findWavetable(id: string | null | undefined): Wavetable | null {
  if (!id) return null;
  ensureLoaded();
  return customTables.find((table) => table.id === id) ?? null;
}

export function designWavetable(input: { name: string; harmonics: number[] }): Wavetable {
  return {
    id: `wavetable-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
    name: input.name.trim().slice(0, 60) || "Custom table",
    harmonics: normalizeHarmonics(input.harmonics),
  };
}

export function saveCustomWavetable(table: Wavetable): void {
  ensureLoaded();
  loaded = true;
  customTables = [table, ...customTables.filter((item) => item.id !== table.id)];
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(CUSTOM_KEY, JSON.stringify(customTables));
  } catch {
    /* private mode / quota */
  }
}

/** PeriodicWave coefficients for WebAudio: index n is partial n. */
export function wavetableCoefficients(table: Wavetable): {
  real: Float32Array<ArrayBuffer>;
  imag: Float32Array<ArrayBuffer>;
} {
  const real = new Float32Array(new ArrayBuffer((HARMONIC_COUNT + 1) * 4));
  const imag = new Float32Array(new ArrayBuffer((HARMONIC_COUNT + 1) * 4));
  table.harmonics.forEach((value, index) => {
    const partial = index + 1;
    if (partial <= HARMONIC_COUNT) imag[partial] = Math.max(0, Math.min(1, value));
  });
  return { real, imag };
}

/** Preview samples in -1..1, normalised so the table does not clip the drawing. */
export function wavetablePreview(table: Wavetable, samples = 96): number[] {
  const active = table.harmonics.some((value) => value > 0);
  const peak = Math.max(
    1,
    table.harmonics.reduce((sum, value) => sum + Math.max(0, value), 0)
  );
  return Array.from({ length: samples }, (_, index) => {
    const t = index / Math.max(1, samples - 1);
    if (!active) return 0;
    let value = 0;
    table.harmonics.forEach((amplitude, harmonic) => {
      value += amplitude * Math.sin(2 * Math.PI * (harmonic + 1) * t);
    });
    return Math.max(-1, Math.min(1, value / peak));
  });
}

export const WAVETABLE_HARMONICS = HARMONIC_COUNT;
