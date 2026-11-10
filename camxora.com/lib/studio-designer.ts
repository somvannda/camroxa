/**
 * Plugin designer (S45).
 *
 * "Create new plugin" is not a form: the Magic Bar switches to design mode, the
 * prompt is sent like any other generation, and the result is a plugin that lands
 * in the user's plugin library — never inserted automatically.
 *
 * The designer itself is deterministic and local: it reads the prompt's intent,
 * names the plugin from the description, and picks a small set of controls from
 * one audio family. No credits are spent and nothing is generated that the audio
 * engine cannot actually run.
 */

import type {
  CustomPlugin,
  CustomPluginFamily,
  ParamDef,
} from "@/lib/studio-plugins";

const STOPWORDS = new Set([
  "a",
  "an",
  "the",
  "with",
  "and",
  "or",
  "for",
  "to",
  "of",
  "in",
  "on",
  "at",
  "by",
  "from",
  "me",
  "my",
  "i",
  "it",
  "its",
  "that",
  "this",
  "please",
  "make",
  "build",
  "create",
  "new",
  "plugin",
  "plugins",
  "effect",
  "effects",
  "audio",
  "processor",
  "here",
  "what",
  "have",
  "mind",
  "here's",
  "heres",
  "like",
  "want",
  "need",
  "some",
  "into",
  "as",
  "is",
  "be",
  "so",
]);

const ADJECTIVES = new Set([
  "warm",
  "bright",
  "dark",
  "soft",
  "subtle",
  "gentle",
  "aggressive",
  "heavy",
  "crunchy",
  "smooth",
  "lush",
  "wide",
  "tight",
  "punchy",
  "clean",
  "dirty",
  "vintage",
  "modern",
  "airy",
  "deep",
  "slow",
  "fast",
]);

type FamilySpec = {
  label: string;
  descriptor: string;
  keywords: string[];
  params: (prompt: string) => ParamDef[];
};

const FAMILIES: Record<CustomPluginFamily, FamilySpec> = {
  saturation: {
    label: "saturation",
    descriptor: "tape-saturation",
    keywords: [
      "saturat",
      "tape",
      "drive",
      "overdrive",
      "distort",
      "grit",
      "crunch",
      "warm",
      "harmonic",
      "console",
      "analog",
      "analogue",
    ],
    params: (prompt) => {
      const gentle = /\b(gentle|subtle|soft|mild|light)\b/.test(prompt);
      const heavy = /\b(heavy|aggressive|harsh|extreme|crushing)\b/.test(prompt);
      return [
        {
          key: "drive",
          label: "Drive",
          min: 0,
          max: 100,
          default: heavy ? 72 : gentle ? 26 : 38,
          unit: "%",
          tier: "primary",
        },
        {
          key: "tone",
          label: "Tone",
          min: 400,
          max: 12000,
          default: /dark|dull|soft/.test(prompt) ? 4200 : /bright|crisp|airy/.test(prompt) ? 9500 : 6800,
          unit: "hz",
          tier: "primary",
        },
        {
          key: "lowCut",
          label: "Low Cut",
          min: 20,
          max: 2000,
          default: /low cut|high.?pass|thin/.test(prompt) ? 140 : 80,
          unit: "hz",
          tier: "secondary",
        },
        {
          key: "mix",
          label: "Mix",
          min: 0,
          max: 100,
          default: 100,
          unit: "%",
          tier: "secondary",
        },
      ];
    },
  },
  space: {
    label: "space",
    descriptor: "reverb",
    keywords: [
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
    params: (prompt) => [
      {
        key: "decay",
        label: "Decay",
        min: 0.2,
        max: 20,
        default: /\b(long|huge|cathedral|vast)\b/.test(prompt) ? 7.5 : /\b(short|small|tight)\b/.test(prompt) ? 1.1 : 3.2,
        unit: "s",
        tier: "primary",
      },
      {
        key: "mix",
        label: "Mix",
        min: 0,
        max: 100,
        default: /\b(subtle|gentle|light)\b/.test(prompt) ? 16 : 30,
        unit: "%",
        tier: "primary",
      },
      {
        key: "width",
        label: "Width",
        min: 0,
        max: 200,
        default: 120,
        unit: "%",
        tier: "secondary",
      },
      {
        key: "lowCut",
        label: "Low Cut",
        min: 20,
        max: 2000,
        default: 160,
        unit: "hz",
        tier: "secondary",
      },
    ],
  },
  movement: {
    label: "movement",
    descriptor: "modulation",
    keywords: [
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
    params: () => [
      { key: "rate", label: "Rate", min: 0.05, max: 10, default: 0.8, unit: "hz", tier: "primary" },
      { key: "depth", label: "Depth", min: 0, max: 100, default: 40, unit: "%", tier: "primary" },
      { key: "mix", label: "Mix", min: 0, max: 100, default: 32, unit: "%", tier: "primary" },
    ],
  },
  dynamics: {
    label: "dynamics",
    descriptor: "dynamics",
    keywords: [
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
    params: (prompt) => [
      {
        key: "threshold",
        label: "Thresh",
        min: -60,
        max: 0,
        default: /\b(gentle|subtle|soft)\b/.test(prompt) ? -26 : -18,
        unit: "db",
        tier: "primary",
      },
      { key: "ratio", label: "Ratio", min: 1, max: 20, default: 4, unit: "ratio", tier: "primary" },
      { key: "attack", label: "Attack", min: 0, max: 200, default: 12, unit: "ms", tier: "primary" },
      { key: "release", label: "Release", min: 5, max: 1000, default: 140, unit: "ms", tier: "secondary" },
      { key: "gain", label: "Gain", min: -12, max: 24, default: 2, unit: "db", tier: "secondary" },
    ],
  },
  filter: {
    label: "filter",
    descriptor: "filter",
    keywords: [
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
    params: (prompt) => [
      {
        key: "lowCut",
        label: "Low Cut",
        min: 20,
        max: 2000,
        default: /\b(low|mud|rumble|bass)\b/.test(prompt) ? 180 : 100,
        unit: "hz",
        tier: "primary",
      },
      {
        key: "highCut",
        label: "High Cut",
        min: 1000,
        max: 20000,
        default: /\b(hiss|harsh|bright)\b/.test(prompt) ? 9000 : 14000,
        unit: "hz",
        tier: "primary",
      },
      { key: "resonance", label: "Resonance", min: 0.1, max: 18, default: 1, tier: "secondary" },
    ],
  },
};

const FAMILY_ORDER: CustomPluginFamily[] = ["saturation", "filter", "space", "movement", "dynamics"];

function scoreFamily(family: CustomPluginFamily, prompt: string): number {
  return FAMILIES[family].keywords.reduce((score, keyword) => {
    const pattern = keyword.includes(".?")
      ? new RegExp(`\\b${keyword}`, "i")
      : new RegExp(`\\b${keyword}\\w*`, "i");
    return score + (pattern.test(prompt) ? 1 : 0);
  }, 0);
}

export function familyForPrompt(prompt: string): CustomPluginFamily {
  let best: CustomPluginFamily = "saturation";
  let bestScore = -1;
  for (const family of FAMILY_ORDER) {
    const score = scoreFamily(family, prompt);
    if (score > bestScore) {
      best = family;
      bestScore = score;
    }
  }
  return best;
}

function meaningfulWords(prompt: string): string[] {
  return prompt
    .toLowerCase()
    .replace(/[^a-z0-9'’\s-]/g, " ")
    .split(/\s+/)
    .map((word) => word.replace(/^['’-]+|['’-]+$/g, ""))
    .filter((word) => word.length > 1 && !STOPWORDS.has(word));
}

function titleCase(word: string): string {
  return word.charAt(0).toUpperCase() + word.slice(1);
}

/** "A warm tape saturation plugin…" → "Warm Tape". */
export function nameForPrompt(prompt: string, family: CustomPluginFamily): string {
  const words = meaningfulWords(prompt).filter(
    (word) => !/^(plugin|effect|audio|processor|saturation|reverb|compression|chorus|filter)$/.test(word)
  );
  const pick = words.slice(0, 2);
  if (pick.length === 0) {
    return FAMILY_FALLBACK_NAME[family];
  }
  if (pick.length === 1) {
    const adjective = words.find((word) => ADJECTIVES.has(word));
    return titleCase(`${adjective && adjective !== pick[0] ? adjective : "Soft"} ${pick[0]}`);
  }
  return pick.map(titleCase).join(" ");
}

const FAMILY_FALLBACK_NAME: Record<CustomPluginFamily, string> = {
  saturation: "Warm Tape",
  space: "Deep Space",
  movement: "Slow Drift",
  dynamics: "Soft Glue",
  filter: "Clean Cut",
};

function slug(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 32);
}

/** djb2, so the same prompt gives the same plugin id. */
function hash(value: string): string {
  let h = 5381;
  for (let i = 0; i < value.length; i += 1) {
    h = ((h << 5) + h + value.charCodeAt(i)) >>> 0;
  }
  return h.toString(36);
}

export type DesignResult = {
  plugin: CustomPlugin;
  /** The assistant's pre-build message (S45: restate, constrain, ask). */
  restate: string;
  /** The completion message after "Build it". */
  completion: string;
};

export function designPlugin(prompt: string, existingNames: string[] = []): DesignResult {
  const text = prompt.trim();
  const family = familyForPrompt(text);
  const spec = FAMILIES[family];
  let name = nameForPrompt(text, family);
  if (existingNames.some((existing) => existing.toLowerCase() === name.toLowerCase())) {
    let index = 2;
    while (existingNames.some((existing) => existing.toLowerCase() === `${name} ${index}`.toLowerCase())) {
      index += 1;
    }
    name = `${name} ${index}`;
  }
  const params = spec.params(text);
  const plugin: CustomPlugin = {
    id: `custom-${slug(name)}-${hash(`${name}:${text}`)}`,
    name,
    description: `Designed from: “${text}”`,
    family,
    params,
    defaults: Object.fromEntries(params.map((param) => [param.key, param.default])),
    prompt: text,
  };
  const controls = params
    .slice(0, 3)
    .map((param) => param.label)
    .join(", ");
  const toneWord = meaningfulWords(text).find((word) => ADJECTIVES.has(word));
  const descriptor = `${toneWord ? `${toneWord} ` : ""}${spec.descriptor}`;
  return {
    plugin,
    restate: `I can build a ${descriptor} audio effect with adjustable ${controls} controls. The new plugin will be saved to your plugin library rather than automatically inserted. Build it?`,
    completion: `${name} is ready with ${controls} controls. Add it to a track to use it.`,
  };
}

/** The card subtitle from S45: kind + verb. */
export const DESIGN_CARD_SUBTITLE = "Audio effect · Drag onto a track";

/** Prompt seeded when design mode opens (S45). */
export const DESIGN_PROMPT = "Make me a new plugin. Here's what I have in mind: ";
