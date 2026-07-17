/** Format onboarding keywords/tags for YouTube Studio paste fields. */

export function formatYoutubeCommaField(items: string[], maxChars?: number): string {
  const text = items.map((item) => item.trim()).filter(Boolean).join(", ");
  if (!maxChars || text.length <= maxChars) {
    return text;
  }
  const trimmed = text.slice(0, maxChars);
  const lastComma = trimmed.lastIndexOf(", ");
  return lastComma > 0 ? trimmed.slice(0, lastComma) : trimmed;
}

/** Comma-separated string for YouTube channel keywords field. */
export function formatYoutubeKeywords(items: string[]): string {
  return formatYoutubeCommaField(items);
}

/** Comma-separated string for YouTube tags field (500-char limit). */
export function formatYoutubeTags(items: string[]): string {
  return formatYoutubeCommaField(items, 500);
}

export function parseYoutubeCommaInput(text: string): string[] {
  return text
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
