/**
 * Plugin designer (S45) — now backed by Suno's authoring agent.
 *
 * The reference designer is not a form: "Create new plugin" switches the Magic
 * Bar to design mode, the prompt goes to an authoring agent, and the finished
 * DSP plugin lands in the plugin library. Camxora mirrors that flow because the
 * agent is the only way to create a plugin Suno can actually load: the agent
 * returns a descriptor, musicapi saves it as a library version, and the chain
 * entry references `catalogPluginId` + `pluginVersionId`.
 *
 * This module owns the pure part: restating the request before spending credits,
 * and converting the agent descriptor into the local `CustomPlugin` snapshot the
 * dock and the audio engine use.
 */

import type {
  CustomPlugin,
  CustomPluginFamily,
  ParamDef,
} from "@/lib/studio-plugins";

/** The descriptor fields the authoring job returns (verified live 2026-11-13). */
export type AuthoredPluginParameter = {
  name: string;
  label?: string;
  default?: number;
  range?: { min?: number; max?: number; step?: number };
  scale?: string;
  unit?: string;
};

export type AuthoredPluginDescriptor = {
  displayName?: string;
  description?: string;
  kind?: string;
  parameters?: AuthoredPluginParameter[];
  [key: string]: unknown;
};

const FAMILY_KEYWORDS: Record<CustomPluginFamily, string[]> = {
  saturation: [
    "satur",
    "tape",
    "drive",
    "overdrive",
    "distort",
    "grit",
    "crunch",
    "warm",
    "harmon",
    "console",
    "analog",
    "analogue",
  ],
  space: [
    "reverb",
    "space",
    "hall",
    "room",
    "ambien",
    "cavern",
    "echo",
    "delay",
    "tail",
    "wash",
    "cathedral",
    "plate",
  ],
  movement: [
    "chorus",
    "movement",
    "modulat",
    "wobble",
    "tremolo",
    "vibrato",
    "flanger",
    "phase",
    "swirl",
    "shimmer",
    "drift",
  ],
  dynamics: [
    "compress",
    "glue",
    "punch",
    "punchy",
    "limit",
    "loud",
    "level",
    "dynamic",
    "squash",
    "control",
  ],
  filter: [
    "filter",
    "cut",
    "eq",
    "tone",
    "high.?pass",
    "low.?pass",
    "resonance",
    "sweep",
    "mud",
    "hiss",
    "noise",
  ],
};

const FAMILY_ORDER: CustomPluginFamily[] = ["saturation", "filter", "space", "movement", "dynamics"];

/** The local audio engine renders a designed plugin by family; this picks one. */
export function familyForPrompt(prompt: string): CustomPluginFamily {
  let best: CustomPluginFamily = "saturation";
  let bestScore = -1;
  for (const family of FAMILY_ORDER) {
    const score = FAMILY_KEYWORDS[family].reduce((total, keyword) => {
      const pattern = keyword.includes(".?")
        ? new RegExp(`\\b${keyword}`, "i")
        : new RegExp(`\\b${keyword}\\w*`, "i");
      return total + (pattern.test(prompt) ? 1 : 0);
    }, 0);
    if (score > bestScore) {
      best = family;
      bestScore = score;
    }
  }
  return best;
}

function unitFromDescriptor(unit: unknown): ParamDef["unit"] {
  const value = String(unit ?? "").toLowerCase();
  if (value === "percent" || value === "percentage" || value === "%") return "%";
  if (value === "hz" || value === "db" || value === "ms" || value === "s" || value === "ratio") {
    return value;
  }
  return "";
}

function uniqueName(name: string, existingNames: string[]): string {
  if (!existingNames.some((existing) => existing.toLowerCase() === name.toLowerCase())) {
    return name;
  }
  let index = 2;
  while (
    existingNames.some((existing) => existing.toLowerCase() === `${name} ${index}`.toLowerCase())
  ) {
    index += 1;
  }
  return `${name} ${index}`;
}

/**
 * Convert a ready authoring job into the local designed-plugin snapshot.
 *
 * Percent controls keep Suno's native 0–1 range; `ParamKnob` renders them as a
 * percentage, so the value that mirrors is exactly the value on screen. Returns
 * null for a descriptor with no usable controls rather than saving a plugin the
 * dock cannot edit.
 */
export function pluginFromAuthoring(
  descriptor: AuthoredPluginDescriptor,
  input: {
    instruction: string;
    pluginId: string;
    pluginVersionId: string;
    existingNames?: string[];
  }
): CustomPlugin | null {
  const rawParams = Array.isArray(descriptor.parameters) ? descriptor.parameters : [];
  const params: ParamDef[] = [];
  for (const raw of rawParams.slice(0, 8)) {
    const key = typeof raw?.name === "string" ? raw.name : "";
    const label = typeof raw?.label === "string" ? raw.label : key;
    const min = Number(raw?.range?.min);
    const max = Number(raw?.range?.max);
    const fallback = Number(raw?.default);
    if (!key || !label || !Number.isFinite(min) || !Number.isFinite(max) || max <= min) continue;
    params.push({
      key,
      label,
      min,
      max,
      default: Number.isFinite(fallback) ? Math.min(max, Math.max(min, fallback)) : min,
      unit: unitFromDescriptor(raw?.unit),
      tier: params.length < 3 ? "primary" : "secondary",
    });
  }
  if (params.length === 0) return null;
  const fallbackName = descriptor.displayName?.trim() || "Designed plugin";
  const name = uniqueName(fallbackName.slice(0, 48), input.existingNames ?? []);
  const description =
    typeof descriptor.description === "string" ? descriptor.description.slice(0, 200) : "";
  return {
    id: `custom-suno-${input.pluginId.replace(/-/g, "").slice(0, 8)}`,
    name,
    description,
    family: familyForPrompt(`${name} ${description}`),
    params,
    defaults: Object.fromEntries(params.map((param) => [param.key, param.default])),
    prompt: input.instruction.slice(0, 400),
    sunoPluginId: input.pluginId,
    sunoPluginVersionId: input.pluginVersionId,
  };
}

/** Pre-build message: restate the request and ask before spending credits. */
export function restateDesign(prompt: string): string {
  const text = prompt.trim().replace(/^make me a new plugin[.:]?\s*/i, "");
  const subject = text || "the effect you described";
  return `I can have the plugin agent build ${subject.startsWith("a ") || subject.startsWith("an ") ? subject : `a plugin for: ${subject}`}. It authors real DSP code, usually takes a few minutes, and uses generation credits. The finished plugin is saved to your plugin library, not inserted automatically. Build it?`;
}

/** The card subtitle from S45: kind + verb. */
export const DESIGN_CARD_SUBTITLE = "Audio effect · Drag onto a track";

/** Prompt seeded when design mode opens (S45). */
export const DESIGN_PROMPT = "Make me a new plugin. Here's what I have in mind: ";
