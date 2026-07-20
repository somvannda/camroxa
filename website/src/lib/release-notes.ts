export type ReleaseNotesSection = {
  title: string;
  items: string[];
};

export type ParsedReleaseNotes = {
  versionHeading: string | null;
  sections: ReleaseNotesSection[];
};

function normalizeNewlines(text: string): string {
  return text.replace(/\r\n/g, "\n").trim();
}

function stripInlineMarkdown(text: string): string {
  return text
   .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[(.+?)\]\([^)]+\)/g, "$1")
    .trim();
}

export function parseReleaseNotes(raw: string): ParsedReleaseNotes {
  const text = normalizeNewlines(raw);
  let versionHeading: string | null = null;
  let body = text;

  const versionMatch = text.match(/^##\s*\[([^\]]+)\]\s*-\s*(.+)$/m);
  if (versionMatch) {
    versionHeading = `${versionMatch[1]} · ${versionMatch[2].trim()}`;
    body = text.replace(/^##[^\n]+\n?/, "").trim();
  }

  const sections: ReleaseNotesSection[] = [];
  const parts = body.split(/\n(?=###\s+)/);

  for (const part of parts) {
    const trimmed = part.trim();
    if (!trimmed) continue;

    const headerMatch = trimmed.match(/^###\s+(.+?)(?:\n|$)/);
    if (!headerMatch) continue;

    const title = headerMatch[1].trim();
    const rest = trimmed.slice(headerMatch[0].length);
    const items = rest
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.startsWith("- "))
      .map((line) => stripInlineMarkdown(line.slice(2).trim()))
      .filter(Boolean);

    if (items.length > 0) {
      sections.push({ title, items });
    }
  }

  if (sections.length === 0) {
    const items = text
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.startsWith("- "))
      .map((line) => stripInlineMarkdown(line.slice(2).trim()))
      .filter(Boolean);

    if (items.length > 0) {
      sections.push({ title: "Release notes", items });
    }
  }

  return { versionHeading, sections };
}

export function looksLikeReleaseNotesMarkdown(text: string): boolean {
  const normalized = normalizeNewlines(text);
  if (/^##\s*\[/m.test(normalized)) return true;
  if (/###\s+(Added|Fixed|Changed|Removed)/im.test(normalized)) return true;
  if (/^\[[\d.]+\]\s*-\s*\d{4}-\d{2}-\d{2}/m.test(normalized)) return true;
  if (/\b(Added|Fixed|Changed)\s+-\s+/i.test(normalized)) return true;
  return false;
}

function extractCollapsedReleaseItems(text: string): string[] {
  const normalized = text.replace(/\s+/g, " ").trim();
  const withoutVersion = normalized.replace(/^\[[^\]]+\]\s*-\s*\d{4}-\d{2}-\d{2}\s+/i, "");
  const addedMatch = withoutVersion.match(/\bAdded\s+-\s+(.+?)(?:\s+\b(?:Fixed|Changed|Removed)\s+-|$)/i);
  if (!addedMatch) {
    return [];
  }
  return addedMatch[1]
    .split(/\s+-\s+/)
    .map((item) => stripInlineMarkdown(item.trim()))
    .filter(Boolean);
}

export function summarizeReleaseNotes(raw: string, maxLength = 220): string {
  const parsed = parseReleaseNotes(raw);
  let items = parsed.sections.find((section) => section.title.toLowerCase() === "added")?.items ?? [];

  if (items.length === 0) {
    items = parsed.sections.flatMap((section) => section.items);
  }

  if (items.length === 0) {
    items = extractCollapsedReleaseItems(raw);
  }

  if (items.length === 0) {
    const cleaned = stripInlineMarkdown(
      raw
        .replace(/^#+\s*/gm, "")
        .replace(/^-\s+/gm, "")
        .replace(/\s+/g, " ")
        .trim(),
    );
    if (!cleaned) return "";
    if (cleaned.length <= maxLength) return cleaned;
    return `${cleaned.slice(0, maxLength - 1).trim()}…`;
  }

  let summary = items.slice(0, 2).join("; ");
  if (items.length > 2) {
    summary = `${summary}; and more.`;
  }

  if (summary.length <= maxLength) {
    return summary;
  }

  return `${summary.slice(0, maxLength - 1).trim()}…`;
}

export function displayPostExcerpt(excerpt: string, content?: string): string {
  const excerptText = normalizeNewlines(excerpt);
  const contentText = normalizeNewlines(content ?? "");

  if (looksLikeReleaseNotesMarkdown(excerptText)) {
    return summarizeReleaseNotes(excerptText);
  }

  if (looksLikeReleaseNotesMarkdown(contentText)) {
    return summarizeReleaseNotes(contentText);
  }

  return excerptText;
}
