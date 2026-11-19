/** Reference SkiaText font catalogue (Vizzy module 22 `h`). */
export const SKIA_FONTS = [
  { title: "Chango", file: "Chango-Regular.ttf" },
  { title: "Eater", file: "Eater-Regular.ttf" },
  { title: "Fondamento", file: "Fondamento-Regular.ttf" },
  { title: "Holtwood One", file: "HoltwoodOneSC-Regular.ttf" },
  { title: "Nosifer", file: "Nosifer-Regular.ttf" },
  { title: "PermanentMarker", file: "PermanentMarker-Regular.ttf" },
  { title: "Rochester", file: "Rochester-Regular.ttf" },
  { title: "SourceSansPro", file: "SourceSansPro-SemiBold.ttf" },
  { title: "Staatliches", file: "Staatliches-Regular.ttf" },
  { title: "TradeWinds", file: "TradeWinds-Regular.ttf" },
] as const;

export const SKIA_FONT_TITLES = SKIA_FONTS.map((font) => font.title);

/**
 * The reference registers SourceSansPro as a four-weight CSS family and canvas
 * text at weight 400 therefore resolves to the Regular cut. It is also the
 * fallback for projects whose exported `font` is empty (most of them).
 */
const DEFAULT_FAMILY = "SourceSansPro";
const DEFAULT_WEIGHTS = [300, 400, 500, 700];

const familyFor = (title: string) => `ReaText ${title}`;

const loaded = new Map<string, Promise<string>>();

/** Uploaded template fonts, keyed by their storage URL. */
const loadedUrls = new Map<string, Promise<string>>();

/**
 * A stable family per URL: the same upload reaches many text items (and HMR
 * re-imports), and registering a fresh family each time would leak faces and
 * defeat the browser's shaper cache. The name must be a single CSS identifier
 * (no space, no leading digit) because `drawText` builds an unquoted
 * `font` shorthand; an invalid family leaves canvas at its default 10px font.
 */
function familyForUrl(url: string): string {
  let hash = 0x811c9dc5;
  for (let index = 0; index < url.length; index += 1) {
    hash ^= url.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return `ReaTextUpload${hash.toString(36)}`;
}

/**
 * Resolves a template's uploaded font. The reference stores the Firebase
 * Storage URL of the project's own TTF/WOFF in the item's `font` field, so the
 * catalogue lookup below would silently substitute SourceSansPro and break the
 * line wrapping the export was authored against.
 */
function loadRemoteFont(url: string): Promise<string> {
  const existing = loadedUrls.get(url);
  if (existing) return existing;

  const family = familyForUrl(url);
  const promise = (async () => {
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`font fetch failed: ${response.status}`);
      const face = new FontFace(family, await response.arrayBuffer());
      await face.load();
      document.fonts.add(face);
      return family;
    } catch {
      // Unreachable upload: the catalogue fallback still draws something.
      return loadSkiaFont(DEFAULT_FAMILY);
    }
  })();
  loadedUrls.set(url, promise);
  return promise;
}

/**
 * Loads a bundled reference font into the document and resolves the CSS family
 * name to use. Repeated requests share one load.
 */
export function loadSkiaFont(title: string): Promise<string> {
  if (!title || title === DEFAULT_FAMILY) {
    const existing = loaded.get(DEFAULT_FAMILY);
    if (existing) return existing;
    const promise = (async () => {
      try {
        await Promise.all(
          DEFAULT_WEIGHTS.map((weight) => document.fonts.load(`${weight} 45px "${DEFAULT_FAMILY}"`)),
        );
      } catch {
        // Keep the family name even if an asset is missing: canvas falls back.
      }
      return DEFAULT_FAMILY;
    })();
    loaded.set(DEFAULT_FAMILY, promise);
    return promise;
  }

  // Templates with a project font store the upload's absolute URL in `font`.
  const url = title.trim();
  if (/^https?:\/\//i.test(url)) return loadRemoteFont(url);

  const entry = SKIA_FONTS.find((font) => font.title === title);
  if (!entry) {
    // A plain family name (e.g. "Georgia") is a locally installed face. The
    // reference only ships its own catalogue, but a supplied Google Fonts URL is
    // not always reachable, so allow a real local serif instead of silently
    // substituting the sans fallback.
    const local = title.trim();
    if (!local) return loadSkiaFont(DEFAULT_FAMILY);
    return document.fonts
      .load(`45px ${local}`)
      .catch(() => {
        // Canvas still tries the family; a missing face falls back at draw time.
      })
      .then(() => local);
  }
  const existing = loaded.get(entry.title);
  if (existing) return existing;

  const family = familyFor(entry.title);
  const promise = (async () => {
    try {
      const face = new FontFace(family, `url(/fonts/${entry.file})`);
      await face.load();
      document.fonts.add(face);
    } catch {
      // Keep the family name even if the asset is missing: canvas falls back.
    }
    return family;
  })();
  loaded.set(entry.title, promise);
  return promise;
}
