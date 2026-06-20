type ChatMessage = { role: "system" | "user" | "assistant"; content: string };

type SongDraft = { title: string; album: string; lyrics: string };

function extractJson(text: string) {
  const s = String(text || "");
  const start = s.indexOf("{");
  const end = s.lastIndexOf("}");
  if (start < 0 || end < 0 || end <= start) return null;
  try {
    return JSON.parse(s.slice(start, end + 1));
  } catch {
    return null;
  }
}

async function chatCompletion(input: { apiKey: string; model: string; temperature: number; messages: ChatMessage[] }) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), 90_000);
  const res = await fetch("https://api.deepseek.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${input.apiKey}`,
    },
    body: JSON.stringify({
      model: input.model,
      temperature: input.temperature,
      messages: input.messages,
      stream: false,
    }),
    signal: controller.signal,
  }).finally(() => clearTimeout(t));

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`DeepSeek error ${res.status}: ${body.slice(0, 400)}`);
  }

  const json = (await res.json()) as {
    choices: { message: { content: string } }[];
  };
  const content = json.choices?.[0]?.message?.content;
  if (!content) throw new Error("DeepSeek returned empty content");
  return content;
}

function normalize(s: string) {
  return String(s || "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

function opening2(lyrics: string) {
  const isHeader = (l: string) => /^\[[^\]]+\]$/.test(l);
  const lines = String(lyrics || "")
    .split("\n")
    .map((x) => x.trim())
    .filter((l) => l && !isHeader(l))
    .slice(0, 2);
  return lines.join("\n");
}

function lyricStats(lyrics: string) {
  const lines = String(lyrics || "")
    .split("\n")
    .map((x) => x.trim());
  const isHeader = (l: string) => /^\[[^\]]+\]$/.test(l);
  const contentLines = lines.filter((l) => l && !isHeader(l));
  const headers = lines.filter((l) => l && isHeader(l));
  const headerText = headers.map((h) => h.toLowerCase());
  const count = (needle: string) => headerText.filter((h) => h.includes(needle)).length;
  return {
    contentLineCount: contentLines.length,
    headerCount: headers.length,
    verseCount: count("verse"),
    chorusCount: count("chorus"),
    bridgeCount: count("bridge"),
  };
}

function injectOpening(lyrics: string, opening: string) {
  const want = String(opening || "")
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean)
    .slice(0, 2);
  if (want.length < 2) return lyrics;
  const isHeader = (l: string) => /^\[[^\]]+\]$/.test(l.trim());
  const lines = String(lyrics || "").split("\n");
  const out: string[] = [];
  let replaced = 0;
  for (const line of lines) {
    if (replaced < 2 && line.trim() && !isHeader(line)) {
      out.push(want[replaced] ?? line);
      replaced += 1;
    } else {
      out.push(line);
    }
  }
  if (replaced < 2) return `${want.join("\n")}\n\n${String(lyrics || "").trim()}`;
  return out.join("\n");
}

function parseStructureHeaders(structure: string) {
  const headers = String(structure || "")
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .filter((l) => /^\[[^\]]+\]$/.test(l));
  return headers;
}

function extractHeadersInLyrics(lyrics: string) {
  return String(lyrics || "")
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .filter((l) => /^\[[^\]]+\]$/.test(l));
}

function hasContentBeforeFirstHeader(lyrics: string) {
  const isHeader = (l: string) => /^\[[^\]]+\]$/.test(l);
  const lines = String(lyrics || "")
    .split("\n")
    .map((l) => l.trim());
  for (const l of lines) {
    if (!l) continue;
    if (isHeader(l)) return false;
    return true;
  }
  return false;
}

export async function generateSongDraftWithDeepSeek(input: {
  apiKey: string;
  language: string;
  creativity: number;
  description: string;
  structure: string;
  model?: string;
  uniqueOpening?: boolean;
  strictLevel?: 1 | 2 | 3 | 4 | 5;
  avoidTitles?: string[];
  avoidAlbums?: string[];
  avoidOpenings?: string[];
  forcedTitle?: string;
  forcedAlbum?: string;
  forcedOpening?: string;
}) {
  const model = input.model ?? "deepseek-chat";
  const avoidTitles = (input.avoidTitles ?? []).filter(Boolean).slice(0, 120);
  const avoidAlbums = (input.avoidAlbums ?? []).filter(Boolean).slice(0, 120);
  const avoidOpenings = (input.avoidOpenings ?? []).filter(Boolean).slice(0, 120);
  const strictLevel = input.strictLevel ?? 3;
  const uniqueOpening = Boolean(input.uniqueOpening);

  const avoidTitleSet = new Set(avoidTitles.map(normalize).filter(Boolean));
  const avoidAlbumSet = new Set(avoidAlbums.map(normalize).filter(Boolean));
  const avoidOpeningSet = new Set(avoidOpenings.map(normalize).filter(Boolean));

  const forcedTitle = String(input.forcedTitle || "").trim();
  const forcedAlbum = String(input.forcedAlbum || "").trim();
  const forcedOpening = String(input.forcedOpening || "").trim();
  const expectedHeaders = parseStructureHeaders(input.structure || "");
  const minContentLines = expectedHeaders.length ? Math.max(16, expectedHeaders.length * 4) : 32;

  const rejectLog: string[] = [];
  const pushReject = (attempt: number, reason: string) => {
    rejectLog.push(`#${attempt} ${reason}`);
    if (rejectLog.length > 24) rejectLog.shift();
  };

  const avoidBlock: string[] = [];
  if (strictLevel >= 2 && avoidTitles.length) avoidBlock.push(`Forbidden titles (avoid exact repeats):\n- ${avoidTitles.join("\n- ")}`);
  if (strictLevel >= 3 && avoidAlbums.length) avoidBlock.push(`Forbidden album names (avoid exact repeats):\n- ${avoidAlbums.join("\n- ")}`);
  if ((strictLevel >= 1 || uniqueOpening) && avoidOpenings.length)
    avoidBlock.push(`Forbidden lyric openings (first two lines; avoid exact repeats):\n- ${avoidOpenings.join("\n- ")}`);

  const maxAttempts = 12;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const fixed: string[] = [];
    if (forcedTitle) fixed.push(`- Use EXACT title: ${forcedTitle}`);
    if (forcedAlbum) fixed.push(`- Use EXACT album name: ${forcedAlbum}`);
    if (forcedOpening) fixed.push(`- The first two non-empty lyric lines must be EXACTLY:\n${forcedOpening}`);

    let raw = "";
    try {
      raw = await chatCompletion({
        apiKey: input.apiKey,
        model,
        temperature: Math.min(1.2, Math.max(0.2, input.creativity / 85)),
        messages: [
          {
            role: "system",
            content:
              "You generate music metadata and lyrics. Output MUST be strict JSON with keys: title, album, lyrics. No markdown, no extra text.",
          },
          {
            role: "user",
            content: [
              `Attempt: ${attempt}/${maxAttempts}`,
              `Language: ${input.language}`,
              `Creativity: ${input.creativity}/100`,
              "Song description:",
              input.description || "(empty)",
              "Song structure:",
              input.structure || "(empty)",
              avoidBlock.length ? "Avoid list:" : "",
              avoidBlock.length ? avoidBlock.join("\n\n") : "",
              fixed.length ? "Fixed values:" : "",
              fixed.length ? fixed.join("\n") : "",
              "Constraints:",
              expectedHeaders.length
                ? [
                    "- Use EXACT section headers and EXACT order from Song structure (one header per line)",
                    ...expectedHeaders.map((h) => `  ${h}`),
                    "- Do NOT add Intro/Outro unless Song structure includes them",
                    "- Do NOT add any extra section headers that are not in Song structure",
                    "- Do NOT write any lyrics before the first header",
                  ].join("\n")
                : "- Lyrics must include section labels like [Verse], [Chorus], [Bridge]",
              "- Write a FULL song, not a sketch",
              "- Each section should have 4-8 lyric lines (excluding section labels)",
              `- Total non-empty lyric lines (excluding section labels) must be at least ${minContentLines}`,
              "- Title should be short and catchy",
              "- Album name should be plausible",
              "- Do NOT output any forbidden exact titles/albums/openings",
              "- The first two non-empty lyric lines must be distinctive",
            ].join("\n"),
          },
        ],
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      pushReject(attempt, `api_error: ${msg}`);
      continue;
    }

    const parsed = extractJson(raw) as SongDraft | null;
    if (!parsed?.title || !parsed?.album || !parsed?.lyrics) {
      pushReject(attempt, "bad_json_or_missing_keys");
      continue;
    }

    const title = forcedTitle || String(parsed.title).trim();
    const album = forcedAlbum || String(parsed.album).trim();
    const lyrics = forcedOpening ? injectOpening(String(parsed.lyrics), forcedOpening) : String(parsed.lyrics);

    const stats = lyricStats(lyrics);
    if (stats.contentLineCount < minContentLines) {
      pushReject(attempt, `too_short: contentLines=${stats.contentLineCount} min=${minContentLines}`);
      continue;
    }

    if (expectedHeaders.length) {
      if (hasContentBeforeFirstHeader(lyrics)) {
        const firstLine = String(lyrics || "")
          .split("\n")
          .map((l) => l.trim())
          .filter(Boolean)[0];
        pushReject(attempt, `content_before_first_header: firstLine=${JSON.stringify(firstLine || "")}`);
        continue;
      }
      const gotHeaders = extractHeadersInLyrics(lyrics);
      if (gotHeaders.length !== expectedHeaders.length) {
        const got = gotHeaders.slice(0, 10).join(" ");
        const exp = expectedHeaders.slice(0, 10).join(" ");
        pushReject(attempt, `header_count_mismatch: got=${gotHeaders.length} expected=${expectedHeaders.length} gotHeaders=${JSON.stringify(got)} expectedHeaders=${JSON.stringify(exp)}`);
        continue;
      }
      let mismatch = false;
      let mismatchAt = -1;
      for (let i = 0; i < expectedHeaders.length; i += 1) {
        if (String(gotHeaders[i] || "").trim() !== String(expectedHeaders[i] || "").trim()) {
          mismatch = true;
          mismatchAt = i;
          break;
        }
      }
      if (mismatch) {
        pushReject(
          attempt,
          `header_mismatch_at=${mismatchAt}: got=${JSON.stringify(String(gotHeaders[mismatchAt] || ""))} expected=${JSON.stringify(String(expectedHeaders[mismatchAt] || ""))}`,
        );
        continue;
      }
      const firstNonEmpty = String(lyrics || "")
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean)[0];
      if (firstNonEmpty && firstNonEmpty !== expectedHeaders[0]) {
        pushReject(attempt, `first_line_not_first_header: firstLine=${JSON.stringify(firstNonEmpty)} expectedFirstHeader=${JSON.stringify(expectedHeaders[0])}`);
        continue;
      }
    }

    const violatesOpening = (strictLevel >= 1 || uniqueOpening) && avoidOpeningSet.has(normalize(opening2(lyrics)));
    const violatesTitle = strictLevel >= 2 && avoidTitleSet.has(normalize(title));
    const violatesAlbum = strictLevel >= 3 && avoidAlbumSet.has(normalize(album));

    if (violatesOpening || violatesTitle || violatesAlbum) {
      const parts: string[] = [];
      if (violatesTitle) parts.push("duplicate_title");
      if (violatesAlbum) parts.push("duplicate_album");
      if (violatesOpening) parts.push("duplicate_opening");
      pushReject(attempt, `avoid_list_violation: ${parts.join(",")}`);
      continue;
    }

    return {
      title,
      album,
      lyricsRaw: String(lyrics).trim(),
    };
  }

  const tail = rejectLog.slice(-8).join(" | ");
  throw new Error(`DeepSeek draft rejected after ${maxAttempts} tries. Recent reasons: ${tail || "(no details)"}`);
}
