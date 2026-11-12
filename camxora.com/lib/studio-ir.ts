/**
 * Impulse-response library for the Convolution card (S44).
 *
 * The reference ships a preset browser grouped into rooms/spaces; the captured card
 * shows `Halls › New England Hall` above a 0–2 s impulse preview. These entries are
 * our own IR set (names and decay shapes are ours), used both by the picker and by the
 * DSP to render an impulse with the same character.
 */

export type ImpulseResponse = {
  id: string;
  category: string;
  name: string;
  /** Tail length in seconds. */
  seconds: number;
  /** Higher values decay faster (used by the synthetic impulse). */
  decay: number;
};

export type ImpulseCategory = {
  label: string;
  items: ImpulseResponse[];
};

export const IMPULSE_CATEGORIES: ImpulseCategory[] = [
  {
    label: "Halls",
    items: [
      { id: "new-england-hall", category: "Halls", name: "New England Hall", seconds: 3.6, decay: 2.4 },
      { id: "large-hall", category: "Halls", name: "Large Hall", seconds: 4.5, decay: 2.2 },
      { id: "cathedral", category: "Halls", name: "Cathedral", seconds: 7.5, decay: 3.2 },
    ],
  },
  {
    label: "Rooms",
    items: [
      { id: "small-room", category: "Rooms", name: "Small Room", seconds: 0.8, decay: 4 },
      { id: "studio-room", category: "Rooms", name: "Studio Room", seconds: 1.4, decay: 3 },
    ],
  },
  {
    label: "Plates",
    items: [
      { id: "bright-plate", category: "Plates", name: "Bright Plate", seconds: 2.2, decay: 2.6 },
      { id: "dark-plate", category: "Plates", name: "Dark Plate", seconds: 3, decay: 2 },
    ],
  },
  {
    label: "Chambers",
    items: [{ id: "echo-chamber", category: "Chambers", name: "Echo Chamber", seconds: 2.6, decay: 2.8 }],
  },
  {
    label: "Spaces",
    items: [
      { id: "vocal-booth", category: "Spaces", name: "Vocal Booth", seconds: 0.5, decay: 5 },
      { id: "open-air", category: "Spaces", name: "Open Air", seconds: 5.5, decay: 2.2 },
    ],
  },
  {
    label: "Springs",
    items: [{ id: "vintage-spring", category: "Springs", name: "Vintage Spring", seconds: 2.4, decay: 2.5 }],
  },
];

export const IMPULSE_RESPONSES: ImpulseResponse[] = IMPULSE_CATEGORIES.flatMap(
  (category) => category.items
);

const CUSTOM_KEY = "studio:custom-impulses";
let customResponses: ImpulseResponse[] = [];
let customsLoaded = false;

function ensureCustomsLoaded(): void {
  if (customsLoaded || typeof window === "undefined") return;
  customsLoaded = true;
  try {
    const raw = window.localStorage.getItem(CUSTOM_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return;
    customResponses = parsed
      .map((item) => {
        if (!item || typeof item !== "object") return null;
        const value = item as Record<string, unknown>;
        const seconds = Number(value.seconds);
        const decay = Number(value.decay);
        if (
          typeof value.id !== "string" ||
          typeof value.name !== "string" ||
          !Number.isFinite(seconds) ||
          !Number.isFinite(decay)
        ) {
          return null;
        }
        return {
          id: value.id,
          name: value.name,
          category: "Custom",
          seconds: Math.max(0.1, Math.min(8, seconds)),
          decay: Math.max(0.2, Math.min(10, decay)),
        } satisfies ImpulseResponse;
      })
      .filter((item): item is ImpulseResponse => item !== null);
  } catch {
    /* private mode / corrupt blob: the built-in library still works */
  }
}

export function customImpulseResponses(): ImpulseResponse[] {
  ensureCustomsLoaded();
  return [...customResponses];
}

export function designImpulseResponse(input: {
  name: string;
  seconds: number;
  decay: number;
}): ImpulseResponse {
  return {
    id: `custom-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
    category: "Custom",
    name: input.name.trim().slice(0, 60) || "Custom IR",
    seconds: Math.max(0.1, Math.min(8, input.seconds)),
    decay: Math.max(0.2, Math.min(10, input.decay)),
  };
}

export function saveCustomImpulseResponse(response: ImpulseResponse): void {
  ensureCustomsLoaded();
  customResponses = [response, ...customResponses.filter((item) => item.id !== response.id)];
  customsLoaded = true;
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(CUSTOM_KEY, JSON.stringify(customResponses));
  } catch {
    /* private mode / quota */
  }
}

export function findImpulseResponse(id: string | null | undefined): ImpulseResponse | null {
  if (!id) return null;
  ensureCustomsLoaded();
  return (
    customResponses.find((response) => response.id === id) ??
    IMPULSE_RESPONSES.find((response) => response.id === id) ??
    null
  );
}

/** Display label for the picker breadcrumb: "Halls › New England Hall". */
export function impulseLabel(id: string | null | undefined): string {
  const response = findImpulseResponse(id);
  return response ? `${response.category} › ${response.name}` : "";
}

/** Deterministic envelope for the card preview (0..1 amplitude per sample). */
export function impulseEnvelope(response: ImpulseResponse, samples = 96): number[] {
  const out: number[] = [];
  for (let index = 0; index < samples; index += 1) {
    const t = index / (samples - 1);
    // Sharp attack, exponential tail plus a little early-reflection ripple.
    const env = Math.pow(1 - t, response.decay) * (0.72 + 0.28 * Math.cos(t * 26));
    out.push(Math.max(0, Math.min(1, env)));
  }
  return out;
}
