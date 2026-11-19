/**
 * Reference effect-browser artwork.
 *
 * The shipped Add effect modal renders a small webp per effect. The files are
 * vendored under `public/media/effects` (see scripts/fetch-effect-thumbs.mjs);
 * this maps our catalogue names to them, including the reference's longer
 * display names for a few aliases.
 */
import manifest from "./effect-thumbnails.json";

const normalize = (value: string): string =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "")
    .trim();

const ALIASES: Record<string, string> = {
  blurtriangle: "Triangle blur",
  outline: "Simple Outline",
  dropshadow: "Simple Shadow",
  imagemask: "Mask",
  glow: "Bloom",
};

const byName = new Map<string, string>();
for (const entry of manifest) {
  if (entry.local) byName.set(normalize(entry.name), entry.local);
}

export function effectThumbnail(name: string): string | null {
  const key = normalize(name);
  const alias = ALIASES[key];
  return byName.get(normalize(alias ?? name)) ?? null;
}
