type ChatMessage = { role: "system" | "user"; content: string };

type SongDraft = {
  title: string;
  album: string;
  lyrics: string;
};

function extractJson(text: string) {
  const trimmed = text.trim();
  try {
    return JSON.parse(trimmed);
  } catch {
    const start = trimmed.indexOf("{");
    const end = trimmed.lastIndexOf("}");
    if (start >= 0 && end > start) {
      const slice = trimmed.slice(start, end + 1);
      return JSON.parse(slice);
    }
    throw new Error("Invalid JSON response");
  }
}

async function chatCompletion(opts: {
  apiKey: string;
  model: string;
  messages: ChatMessage[];
  temperature?: number;
}) {
  const res = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${opts.apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: opts.model,
      messages: opts.messages,
      temperature: opts.temperature ?? 0.7,
    }),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`OpenAI error ${res.status}: ${body.slice(0, 400)}`);
  }

  const json = (await res.json()) as {
    choices: { message: { content: string } }[];
  };
  const content = json.choices?.[0]?.message?.content;
  if (!content) throw new Error("OpenAI returned empty content");
  return content;
}

export async function generateSongWithOpenAI(input: {
  apiKey: string;
  language: string;
  creativity: number;
  description: string;
  structure: string;
  modelGenerate?: string;
  modelPolish?: string;
  uniqueOpening?: boolean;
  strictLevel?: 1 | 2 | 3 | 4 | 5;
  avoidTitles?: string[];
  avoidAlbums?: string[];
  avoidOpenings?: string[];
  forcedTitle?: string;
  forcedAlbum?: string;
  forcedOpening?: string;
}) {
  const modelGenerate = input.modelGenerate ?? "gpt-4o-mini";
  const modelPolish = input.modelPolish ?? "gpt-4o-mini";

  const avoidTitles = (input.avoidTitles ?? []).filter(Boolean).slice(0, 120);
  const avoidAlbums = (input.avoidAlbums ?? []).filter(Boolean).slice(0, 120);
  const avoidOpenings = (input.avoidOpenings ?? []).filter(Boolean).slice(0, 120);
  const strictLevel = input.strictLevel ?? 3;
  const uniqueOpening = Boolean(input.uniqueOpening);

  const avoidBlock: string[] = [];
  if (strictLevel >= 2 && avoidTitles.length) avoidBlock.push(`Forbidden titles (avoid exact repeats):\n- ${avoidTitles.join("\n- ")}`);
  if (strictLevel >= 3 && avoidAlbums.length) avoidBlock.push(`Forbidden album names (avoid exact repeats):\n- ${avoidAlbums.join("\n- ")}`);
  if ((strictLevel >= 1 || uniqueOpening) && avoidOpenings.length)
    avoidBlock.push(`Forbidden lyric openings (first two lines; avoid exact repeats):\n- ${avoidOpenings.join("\n- ")}`);

  const forcedTitle = String(input.forcedTitle || "").trim();
  const forcedAlbum = String(input.forcedAlbum || "").trim();
  const forcedOpening = String(input.forcedOpening || "").trim();

  const norm = (s: string) => String(s || "").toLowerCase().replace(/\s+/g, " ").trim();
  const avoidTitleSet = new Set(avoidTitles.map(norm).filter(Boolean));
  const avoidAlbumSet = new Set(avoidAlbums.map(norm).filter(Boolean));
  const avoidOpeningSet = new Set(avoidOpenings.map(norm).filter(Boolean));

  function opening2(lyrics: string) {
    const lines = String(lyrics || "")
      .split("\n")
      .map((x) => x.trim())
      .filter(Boolean)
      .slice(0, 2);
    return lines.join("\n");
  }

  function injectOpening(lyrics: string, opening: string) {
    const want = String(opening || "")
      .split("\n")
      .map((x) => x.trim())
      .filter(Boolean)
      .slice(0, 2);
    if (want.length < 2) return lyrics;
    const lines = String(lyrics || "").split("\n");
    const out: string[] = [];
    let replaced = 0;
    for (const line of lines) {
      if (replaced < 2 && line.trim()) {
        out.push(want[replaced] ?? line);
        replaced += 1;
      } else {
        out.push(line);
      }
    }
    if (replaced < 2) return `${want.join("\n")}\n\n${String(lyrics || "").trim()}`;
    return out.join("\n");
  }

  const maxAttempts = 5;
  let draft: SongDraft | null = null;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const fixed: string[] = [];
    if (forcedTitle) fixed.push(`- Use EXACT title: ${forcedTitle}`);
    if (forcedAlbum) fixed.push(`- Use EXACT album name: ${forcedAlbum}`);
    if (forcedOpening) fixed.push(`- The first two non-empty lyric lines must be EXACTLY:\n${forcedOpening}`);

    const draftText = await chatCompletion({
      apiKey: input.apiKey,
      model: modelGenerate,
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
            "- Lyrics must include section labels like [Intro], [Verse], [Chorus], [Bridge], [Outro] when applicable",
            "- Title should be short and catchy",
            "- Album name should be plausible",
            "- Do NOT output any forbidden exact titles/albums/openings",
            "- The first two non-empty lyric lines must be distinctive",
          ].join("\n"),
        },
      ],
    });

    const parsed = extractJson(draftText) as SongDraft;
    if (!parsed?.title || !parsed?.album || !parsed?.lyrics) continue;

    const title = forcedTitle || String(parsed.title).trim();
    const album = forcedAlbum || String(parsed.album).trim();
    const lyrics = forcedOpening ? injectOpening(String(parsed.lyrics), forcedOpening) : String(parsed.lyrics);

    const violatesOpening = (strictLevel >= 1 || uniqueOpening) && avoidOpeningSet.has(norm(opening2(lyrics)));
    const violatesTitle = strictLevel >= 2 && avoidTitleSet.has(norm(title));
    const violatesAlbum = strictLevel >= 3 && avoidAlbumSet.has(norm(album));

    draft = { title, album, lyrics };
    if (!violatesOpening && !violatesTitle && !violatesAlbum) break;
  }

  if (!draft) throw new Error("OpenAI returned incomplete draft");

  const polishedLyrics = await chatCompletion({
    apiKey: input.apiKey,
    model: modelPolish,
    temperature: 0.4,
    messages: [
      {
        role: "system",
        content:
          "Polish song lyrics without changing meaning. Keep section labels and line breaks. Return ONLY the polished lyrics text.",
      },
      { role: "user", content: draft.lyrics },
    ],
  });

  return {
    title: draft.title.trim(),
    album: draft.album.trim(),
    lyricsRaw: draft.lyrics.trim(),
    lyricsPolished: polishedLyrics.trim(),
  };
}

export async function polishLyricsWithOpenAI(input: {
  apiKey: string;
  lyrics: string;
  strength: number;
  model?: string;
}) {
  const model = input.model ?? "gpt-4o-mini";
  const strength = Math.max(0, Math.min(100, input.strength));
  const temperature = 0.15 + (strength / 100) * 0.55;

  const polishedLyrics = await chatCompletion({
    apiKey: input.apiKey,
    model,
    temperature,
    messages: [
      {
        role: "system",
        content:
          "Polish song lyrics: improve flow, rhythm, and clarity while preserving meaning. Keep section labels like [Verse], [Chorus] and keep line breaks. Return ONLY the polished lyrics text.",
      },
      { role: "user", content: input.lyrics },
    ],
  });

  return polishedLyrics.trim();
}
