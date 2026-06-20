function pick<T>(arr: readonly T[]) {
  return arr[Math.floor(Math.random() * arr.length)]!;
}

function normalize(text: string) {
  return String(text || "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

const adjectives = [
  "neon",
  "midnight",
  "electric",
  "golden",
  "silver",
  "crystal",
  "velvet",
  "static",
  "hollow",
  "distant",
  "bright",
  "blurred",
  "wild",
  "quiet",
  "loud",
  "tender",
  "broken",
  "unspoken",
  "secret",
  "reckless",
  "restless",
  "glowing",
  "fading",
  "burning",
  "frozen",
  "sunlit",
  "moonlit",
  "stormy",
  "rainy",
  "endless",
  "timeless",
  "paper",
  "plastic",
  "digital",
  "analog",
  "city",
  "coastal",
  "northern",
  "southern",
  "lunar",
  "solar",
  "magnetic",
  "gravity",
  "cosmic",
  "stellar",
  "chromatic",
  "sapphire",
  "amber",
  "azure",
  "violet",
  "scarlet",
  "obsidian",
  "opal",
  "ruby",
  "emerald",
  "porcelain",
  "carbon",
  "steel",
  "soft",
  "hard",
  "heavy",
  "weightless",
  "future",
  "retro",
  "glitch",
  "perfect",
  "imperfect",
  "fearless",
  "careless",
  "patient",
  "urgent",
  "hidden",
  "open",
  "private",
  "public",
  "parallel",
  "spiral",
  "silent",
  "shattered",
  "wired",
  "wireless",
  "radio",
  "pixel",
  "liquid",
  "solid",
  "electric-blue",
  "rose",
  "blackout",
  "afterglow",
  "high-speed",
  "low-fi",
  "hi-fi",
  "first",
  "last",
  "next",
  "final",
  "rare",
  "common",
  "strange",
  "familiar",
  "haunted",
  "blessed",
  "fragile",
  "iron",
  "paper-thin",
  "deep",
  "shallow",
  "slow",
  "fast",
  "hazy",
  "sharp",
  "warm",
  "cold",
  "unreal",
  "real",
  "new",
  "old",
  "ancient",
  "modern",
  "electric-pink",
  "ultraviolet",
  "infrared",
  "blue",
  "red",
  "white",
  "black",
  "grey",
  "midnight-blue",
  "sunset",
  "dawn",
  "twilight",
  "after-midnight",
  "before-dawn",
  "late-night",
  "early-morning",
  "covert",
  "overt",
  "glimmering",
  "flashing",
  "drifting",
  "steady",
  "wavering",
  "electric-summer",
  "winter",
  "spring",
  "autumn",
  "summer",
  "narrow",
  "wide",
  "open-ended",
  "closed-loop",
  "radiant",
  "dim",
  "synth",
  "bass",
  "brightline",
  "darkwave",
  "dream",
  "night",
  "day",
  "soft-focus",
  "hard-edge",
  "glass",
  "neon-lit",
  "street",
  "ocean",
  "sky",
  "underground",
  "overground",
  "topline",
  "bottomline",
  "heartbeat",
  "heartbeat-fast",
  "heartbeat-slow",
  "electric-heart",
  "paper-heart",
  "silk",
  "velour",
  "chrome",
  "titanium",
  "luminous",
  "shadow",
  "sudden",
  "gentle",
  "blue-hour",
  "gold-hour",
];

const nouns = [
  "city",
  "night",
  "dream",
  "static",
  "signal",
  "pulse",
  "echo",
  "shadow",
  "light",
  "glow",
  "storm",
  "rain",
  "thunder",
  "sky",
  "ocean",
  "river",
  "street",
  "avenue",
  "highway",
  "room",
  "mirror",
  "window",
  "door",
  "key",
  "lock",
  "heart",
  "voice",
  "silence",
  "noise",
  "fire",
  "ice",
  "ember",
  "spark",
  "star",
  "moon",
  "sun",
  "orbit",
  "gravity",
  "comet",
  "neon",
  "circuit",
  "wire",
  "frequency",
  "wave",
  "bassline",
  "melody",
  "hook",
  "chorus",
  "verse",
  "break",
  "drop",
  "build",
  "nightfall",
  "afterglow",
  "midnight",
  "dawn",
  "twilight",
  "rush",
  "kiss",
  "lie",
  "truth",
  "promise",
  "secret",
  "memory",
  "moment",
  "map",
  "road",
  "corner",
  "edge",
  "distance",
  "horizon",
  "orbit",
  "arcade",
  "station",
  "platform",
  "taxi",
  "train",
  "radio",
  "camera",
  "snapshot",
  "polaroid",
  "page",
  "letter",
  "postcard",
  "headline",
  "story",
  "chapter",
  "refrain",
  "heartbeat",
  "breath",
  "sigh",
  "glimmer",
  "shadowline",
  "sunrise",
  "sunset",
  "blueprint",
  "pattern",
  "signal",
  "noise-floor",
  "synthline",
  "kick",
  "snare",
  "hi-hat",
  "groove",
  "tempo",
  "chord",
  "minor-key",
  "major-key",
  "hotel",
  "rooftop",
  "basement",
  "alley",
  "bridge",
  "tunnel",
  "neighborhood",
  "district",
  "coast",
  "harbor",
  "lighthouse",
  "air",
  "dust",
  "smoke",
  "glass",
  "chrome",
  "velvet",
  "silk",
  "paper",
  "plastic",
  "pixel",
  "glitch",
  "drift",
  "loop",
  "strobe",
  "laser",
  "fog",
  "haze",
  "sparkle",
  "gravity",
  "constellation",
  "satellite",
  "nightdrive",
  "handshake",
  "goodbye",
  "hello",
  "afterparty",
  "hangover",
  "blue-hour",
  "gold-hour",
];

const verbs = [
  "chase",
  "follow",
  "forget",
  "remember",
  "hold",
  "leave",
  "find",
  "lose",
  "burn",
  "freeze",
  "drift",
  "run",
  "hide",
  "show",
  "turn",
  "fade",
  "glow",
  "fall",
  "rise",
  "wait",
  "breathe",
  "call",
  "answer",
  "promise",
  "break",
  "build",
  "dance",
  "move",
  "stay",
  "go",
];

const places = [
  "on the rooftop",
  "in the hallway",
  "by the river",
  "under streetlights",
  "in the backseat",
  "at the station",
  "in the club",
  "on the coastline",
  "beneath the neon",
  "under the moon",
  "in the quiet room",
  "inside the static",
  "between the lines",
  "in the dark",
  "in the blue hour",
];

const feelings = [
  "like home",
  "for the first time",
  "like we never left",
  "until the morning",
  "without a warning",
  "in perfect sync",
  "on repeat",
  "in slow motion",
  "in the afterglow",
  "in the silence",
  "in the noise",
  "under my skin",
];

export function generateTitleCandidates(count: number) {
  const out: string[] = [];
  const seen = new Set<string>();
  const target = Math.max(1, Math.floor(count));
  let attempts = 0;
  while (out.length < target && attempts < target * 30) {
    attempts += 1;
    const a = pick(adjectives);
    const n = pick(nouns);
    const n2 = pick(nouns);
    const v = pick(verbs);
    const place = pick(places);
    const feel = pick(feelings);
    const pattern = attempts % 12;
    const text =
      pattern === 0
        ? `When the ${a} ${n} calls`
        : pattern === 1
          ? `${a} ${n}`
          : pattern === 2
            ? `Echoes of the ${a} ${n}`
            : pattern === 3
              ? `After the ${a} ${n}`
              : pattern === 4
                ? `Under the ${a} ${n}`
                : pattern === 5
                  ? `Between ${a} ${n} and ${n2}`
                  : pattern === 6
                    ? `This is how it feels ${feel}`
                    : pattern === 7
                      ? `I ${v} ${place}`
                      : pattern === 8
                        ? `We ${v} through the ${a} ${n}`
                        : pattern === 9
                          ? `Don't let the ${a} ${n} fade`
                          : pattern === 10
                            ? `I ${v} and you stay ${feel}`
                            : `Under streetlights, we ${v} again`;
    const norm = normalize(text);
    if (!norm || seen.has(norm)) continue;
    seen.add(norm);
    out.push(text);
  }
  return out;
}

export function generateAlbumCandidates(count: number) {
  const out: string[] = [];
  const seen = new Set<string>();
  const target = Math.max(1, Math.floor(count));
  let attempts = 0;
  while (out.length < target && attempts < target * 30) {
    attempts += 1;
    const a = pick(adjectives);
    const n = pick(nouns);
    const n2 = pick(nouns);
    const pattern = attempts % 6;
    const text =
      pattern === 0
        ? `Stories from the ${a} ${n}`
        : pattern === 1
          ? `Letters in the ${a} ${n}`
          : pattern === 2
            ? `The ${a} ${n} Collection`
            : pattern === 3
              ? `${a} ${n} and ${n2}`
              : pattern === 4
                ? `Inside the ${a} ${n}`
                : `Between ${a} ${n} and ${n2}`;
    const norm = normalize(text);
    if (!norm || seen.has(norm)) continue;
    seen.add(norm);
    out.push(text);
  }
  return out;
}

export function generateOpeningPairs(count: number) {
  const out: Array<{ line1: string; line2: string }> = [];
  const seen = new Set<string>();
  const target = Math.max(1, Math.floor(count));
  let attempts = 0;
  while (out.length < target && attempts < target * 40) {
    attempts += 1;
    const a = pick(adjectives);
    const n = pick(nouns);
    const v = pick(verbs);
    const place = pick(places);
    const who = pick([
      "I",
      "We",
      "You",
      "Tonight",
      "Somewhere",
      "In my head",
      "In your eyes",
      "Under the neon",
      "After midnight",
    ]);
    const mood = pick([
      "love",
      "heartbreak",
      "longing",
      "regret",
      "hope",
      "jealousy",
      "desire",
      "nostalgia",
      "loneliness",
      "euphoria",
    ]);
    const time = pick([
      "tonight",
      "right now",
      "in the morning",
      "after midnight",
      "before dawn",
      "all summer",
      "all winter",
      "for one more hour",
    ]);
    const line1 =
      who === "I" || who === "We" || who === "You"
        ? `${who} ${v} the ${a} ${n} ${place}.`
        : `${who}, the ${a} ${n} feels too close ${time}.`;
    const line2 = pick([
      `My ${mood} is louder than the kick drum ${time}.`,
      `Your voice turns into static, and I still hear it ${time}.`,
      `I taste the goodbye in the air, sweet and cruel ${time}.`,
      `We promised we'd be fearless, then we blinked ${time}.`,
      `I keep the truth on mute, but it leaks through ${time}.`,
      `Hold me like a secret you can't keep ${time}.`,
      `If this is love, why does it hurt so clean ${time}?`,
      `I miss the version of us that never breaks ${time}.`,
      `Tell me it's real, even if it's only for the chorus ${time}.`,
      `I let the night decide who we are ${time}.`,
    ]);
    const norm = normalize(`${line1} ${line2}`);
    if (!norm || seen.has(norm)) continue;
    seen.add(norm);
    out.push({ line1, line2 });
  }
  return out;
}
