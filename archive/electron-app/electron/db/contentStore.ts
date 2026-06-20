import * as pg from "pg";

export type DbCfg = { host: string; port: number; user: string; password: string; database: string };

export type DbPromptTemplate = { id: string; name: string; scene: string; negativePrompt: string; updatedAt: string };
export type DbSongStructure = { id: string; name: string; text: string; updatedAt: string };
export type DbSongDescription = { id: string; name: string; text: string; updatedAt: string };
export type DbCarModel = {
  id: string;
  make: string;
  model: string;
  trim: string;
  year: number;
  category: string;
  updatedAt: string;
};
export type DbTextStyle = {
  id: string;
  name: string;
  presetId?: string;
  paletteId?: string;
  title: string;
  subtitle: string;
  subtitle2: string;
  prompt: string;
  opacity: number;
  position: "top" | "center" | "bottom";
  updatedAt: string;
};

async function connect(cfg: DbCfg) {
  const client = new pg.Client({
    host: cfg.host,
    port: cfg.port,
    user: cfg.user,
    password: cfg.password,
    database: cfg.database,
  });
  await client.connect();
  return client;
}

function nowIso() {
  return new Date().toISOString();
}

export async function listPromptTemplates(cfg: DbCfg): Promise<DbPromptTemplate[]> {
  const client = await connect(cfg);
  try {
    await client.query("update prompt_templates set uid = concat('tpl-', id) where uid is null");
    const res = await client.query(
      "select uid, name, scene, negative_prompt, coalesce(updated_at, created_at) as updated_at from prompt_templates order by coalesce(updated_at, created_at) desc, id desc",
    );
    return res.rows.map((r) => ({
      id: String(r.uid),
      name: String(r.name ?? ""),
      scene: String(r.scene ?? ""),
      negativePrompt: String(r.negative_prompt ?? ""),
      updatedAt: new Date(r.updated_at).toISOString(),
    }));
  } finally {
    await client.end();
  }
}

export async function listCarModels(cfg: DbCfg): Promise<DbCarModel[]> {
  const client = await connect(cfg);
  try {
    await client.query("update car_models set uid = concat('car-', id) where uid is null");
    const res = await client.query(
      "select uid, make, model, trim, year, category, updated_at from car_models order by updated_at desc, id desc",
    );
    return res.rows.map((r) => ({
      id: String(r.uid),
      make: String(r.make ?? ""),
      model: String(r.model ?? ""),
      trim: String(r.trim ?? ""),
      year: Number(r.year ?? 0),
      category: String(r.category ?? ""),
      updatedAt: new Date(r.updated_at).toISOString(),
    }));
  } finally {
    await client.end();
  }
}

export async function upsertCarModel(cfg: DbCfg, item: Omit<DbCarModel, "updatedAt">) {
  const client = await connect(cfg);
  try {
    const updatedAt = nowIso();
    await client.query(
      "insert into car_models(uid, make, model, trim, year, category, updated_at) values ($1,$2,$3,$4,$5,$6,$7) on conflict(uid) do update set make=excluded.make, model=excluded.model, trim=excluded.trim, year=excluded.year, category=excluded.category, updated_at=excluded.updated_at",
      [item.id, item.make, item.model, item.trim, item.year, item.category, updatedAt],
    );
    return { ...item, updatedAt };
  } finally {
    await client.end();
  }
}

export async function deleteCarModel(cfg: DbCfg, id: string) {
  const client = await connect(cfg);
  try {
    await client.query("delete from car_models where uid = $1", [id]);
    return { ok: true as const };
  } finally {
    await client.end();
  }
}

export async function bulkUpsertCarModels(cfg: DbCfg, items: Omit<DbCarModel, "updatedAt">[]) {
  const client = await connect(cfg);
  try {
    const updatedAt = nowIso();
    await client.query("begin");
    for (let i = 0; i < items.length; i += 500) {
      const chunk = items.slice(i, i + 500);
      const values: unknown[] = [];
      const parts: string[] = [];
      for (let j = 0; j < chunk.length; j += 1) {
        const it = chunk[j]!;
        const idx = j * 7;
        parts.push(`($${idx + 1},$${idx + 2},$${idx + 3},$${idx + 4},$${idx + 5},$${idx + 6},$${idx + 7})`);
        values.push(it.id, it.make, it.model, it.trim, it.year, it.category, updatedAt);
      }
      await client.query(
        `insert into car_models(uid, make, model, trim, year, category, updated_at)
         values ${parts.join(",")}
         on conflict(uid) do update set
           make=excluded.make,
           model=excluded.model,
           trim=excluded.trim,
           year=excluded.year,
           category=excluded.category,
           updated_at=excluded.updated_at`,
        values,
      );
    }
    await client.query("commit");
    return { ok: true as const, updatedAt };
  } catch (e) {
    await client.query("rollback").catch(() => undefined);
    throw e;
  } finally {
    await client.end();
  }
}

export async function upsertPromptTemplate(cfg: DbCfg, item: { id: string; name: string; scene: string; negativePrompt: string }) {
  const client = await connect(cfg);
  try {
    const updatedAt = nowIso();
    await client.query(
      "insert into prompt_templates(uid, name, scene, negative_prompt, updated_at) values ($1,$2,$3,$4,$5) on conflict(uid) do update set name=excluded.name, scene=excluded.scene, negative_prompt=excluded.negative_prompt, updated_at=excluded.updated_at",
      [item.id, item.name, item.scene, item.negativePrompt, updatedAt],
    );
    return { ...item, updatedAt };
  } finally {
    await client.end();
  }
}

export async function deletePromptTemplate(cfg: DbCfg, id: string) {
  const client = await connect(cfg);
  try {
    await client.query("delete from prompt_templates where uid = $1", [id]);
    return { ok: true as const };
  } finally {
    await client.end();
  }
}

export async function listSongStructures(cfg: DbCfg): Promise<DbSongStructure[]> {
  const client = await connect(cfg);
  try {
    await client.query("update song_structures set uid = concat('struct-', id) where uid is null");
    const res = await client.query(
      "select uid, name, content, match_key, updated_at from song_structures order by updated_at desc, id desc",
    );
    return res.rows.map((r) => ({
      id: String(r.uid),
      name: String(r.name ?? ""),
      text: String(r.content ?? ""),
      matchKey: String(r.match_key ?? ""),
      updatedAt: new Date(r.updated_at).toISOString(),
    }));
  } finally {
    await client.end();
  }
}

export async function upsertSongStructure(cfg: DbCfg, item: { id: string; name: string; text: string; matchKey?: string }) {
  const client = await connect(cfg);
  try {
    const updatedAt = nowIso();
    await client.query(
      "insert into song_structures(uid, name, content, match_key, updated_at) values ($1,$2,$3,$4,$5) on conflict(uid) do update set name=excluded.name, content=excluded.content, match_key=excluded.match_key, updated_at=excluded.updated_at",
      [item.id, item.name, item.text, String(item.matchKey ?? ""), updatedAt],
    );
    return { ...item, updatedAt };
  } finally {
    await client.end();
  }
}

export async function deleteSongStructure(cfg: DbCfg, id: string) {
  const client = await connect(cfg);
  try {
    await client.query("delete from song_structures where uid = $1", [id]);
    return { ok: true as const };
  } finally {
    await client.end();
  }
}

export async function listSongDescriptions(cfg: DbCfg): Promise<DbSongDescription[]> {
  const client = await connect(cfg);
  try {
    await client.query("update song_descriptions set uid = concat('desc-', id) where uid is null");
    const res = await client.query(
      "select uid, name, content, match_key, updated_at from song_descriptions order by updated_at desc, id desc",
    );
    return res.rows.map((r) => ({
      id: String(r.uid),
      name: String(r.name ?? ""),
      text: String(r.content ?? ""),
      matchKey: String(r.match_key ?? ""),
      updatedAt: new Date(r.updated_at).toISOString(),
    }));
  } finally {
    await client.end();
  }
}

export async function upsertSongDescription(cfg: DbCfg, item: { id: string; name: string; text: string; matchKey?: string }) {
  const client = await connect(cfg);
  try {
    const updatedAt = nowIso();
    await client.query(
      "insert into song_descriptions(uid, name, content, match_key, updated_at) values ($1,$2,$3,$4,$5) on conflict(uid) do update set name=excluded.name, content=excluded.content, match_key=excluded.match_key, updated_at=excluded.updated_at",
      [item.id, item.name, item.text, String(item.matchKey ?? ""), updatedAt],
    );
    return { ...item, updatedAt };
  } finally {
    await client.end();
  }
}

export async function deleteSongDescription(cfg: DbCfg, id: string) {
  const client = await connect(cfg);
  try {
    await client.query("delete from song_descriptions where uid = $1", [id]);
    return { ok: true as const };
  } finally {
    await client.end();
  }
}

export async function listTextStyles(cfg: DbCfg): Promise<DbTextStyle[]> {
  const client = await connect(cfg);
  try {
    await client.query("update text_styles set uid = concat('style-', id) where uid is null");
    const res = await client.query(
      "select uid, name, preset_id, palette_id, title, subtitle, subtitle2, prompt, opacity, position, updated_at from text_styles order by updated_at desc, id desc",
    );
    return res.rows.map((r) => ({
      id: String(r.uid),
      name: String(r.name ?? ""),
      presetId: String(r.preset_id ?? "") || undefined,
      paletteId: String(r.palette_id ?? "") || undefined,
      title: String(r.title ?? ""),
      subtitle: String(r.subtitle ?? ""),
      subtitle2: String(r.subtitle2 ?? ""),
      prompt: String(r.prompt ?? ""),
      opacity: Number(r.opacity ?? 0.9),
      position: (String(r.position ?? "center") as "top" | "center" | "bottom"),
      updatedAt: new Date(r.updated_at).toISOString(),
    }));
  } finally {
    await client.end();
  }
}

export async function upsertTextStyle(cfg: DbCfg, item: Omit<DbTextStyle, "updatedAt">) {
  const client = await connect(cfg);
  try {
    const updatedAt = nowIso();
    await client.query(
      "insert into text_styles(uid, name, preset_id, palette_id, title, subtitle, subtitle2, prompt, opacity, position, updated_at) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) on conflict(uid) do update set name=excluded.name, preset_id=excluded.preset_id, palette_id=excluded.palette_id, title=excluded.title, subtitle=excluded.subtitle, subtitle2=excluded.subtitle2, prompt=excluded.prompt, opacity=excluded.opacity, position=excluded.position, updated_at=excluded.updated_at",
      [
        item.id,
        item.name,
        String(item.presetId ?? ""),
        String(item.paletteId ?? ""),
        item.title,
        item.subtitle,
        item.subtitle2,
        item.prompt,
        item.opacity,
        item.position,
        updatedAt,
      ],
    );
    return { ...item, updatedAt };
  } finally {
    await client.end();
  }
}

export async function deleteTextStyle(cfg: DbCfg, id: string) {
  const client = await connect(cfg);
  try {
    await client.query("delete from text_styles where uid = $1", [id]);
    return { ok: true as const };
  } finally {
    await client.end();
  }
}

export async function bulkUpsertTextStyles(cfg: DbCfg, items: Omit<DbTextStyle, "updatedAt">[]) {
  const client = await connect(cfg);
  try {
    const updatedAt = nowIso();
    await client.query("begin");
    for (let i = 0; i < items.length; i += 250) {
      const chunk = items.slice(i, i + 250);
      const values: unknown[] = [];
      const parts: string[] = [];
      for (let j = 0; j < chunk.length; j += 1) {
        const it = chunk[j]!;
        const idx = j * 11;
        parts.push(
          `($${idx + 1},$${idx + 2},$${idx + 3},$${idx + 4},$${idx + 5},$${idx + 6},$${idx + 7},$${idx + 8},$${idx + 9},$${idx + 10},$${idx + 11})`,
        );
        values.push(
          it.id,
          it.name,
          String(it.presetId ?? ""),
          String(it.paletteId ?? ""),
          it.title,
          it.subtitle,
          it.subtitle2,
          it.prompt,
          it.opacity,
          it.position,
          updatedAt,
        );
      }
      await client.query(
        `insert into text_styles(uid, name, preset_id, palette_id, title, subtitle, subtitle2, prompt, opacity, position, updated_at)
         values ${parts.join(",")}
         on conflict(uid) do update set
           name=excluded.name,
           preset_id=excluded.preset_id,
           palette_id=excluded.palette_id,
           title=excluded.title,
           subtitle=excluded.subtitle,
           subtitle2=excluded.subtitle2,
           prompt=excluded.prompt,
           opacity=excluded.opacity,
           position=excluded.position,
           updated_at=excluded.updated_at`,
        values,
      );
    }
    await client.query("commit");
    return { ok: true as const, updatedAt };
  } catch (e) {
    await client.query("rollback").catch(() => undefined);
    throw e;
  } finally {
    await client.end();
  }
}

export async function seedBossPresets(cfg: DbCfg) {
  const client = await connect(cfg);
  try {
    const updatedAt = nowIso();
    await client.query("begin");

    const seededFlag = await client.query("select value from app_settings where key = 'seedBossPresetsDone' limit 1");
    const alreadySeeded = String(seededFlag.rows?.[0]?.value ?? "").trim() === "1";
    if (alreadySeeded) {
      await client.query("commit");
      return { ok: true as const };
    }

    const negativeDefault =
      "No text, no typography, no watermark, no logos, no letters, no numbers, no captions, no UI overlays, no signatures, no frames, no borders.";

    const promptRows: Array<{ uid: string; name: string; scene: string; negativePrompt: string }> = [
      {
        uid: "bg-001",
        name: "Cyberpunk Neon 01",
        negativePrompt: negativeDefault,
        scene:
          "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, futuristic sports car in cyberpunk city, neon lights, wet road reflections, trending on artstation, unreal engine render, octane render, cinematic color grading",
      },
      {
        uid: "bg-002",
        name: "Cyberpunk Neon 02",
        negativePrompt: negativeDefault,
        scene:
          "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, hypercar with neon blue and pink accents, smoke and light trails, trending on artstation, unreal engine render, octane render, cinematic color grading",
      },
      {
        uid: "bg-003",
        name: "Cyberpunk Neon 03",
        negativePrompt: negativeDefault,
        scene:
          "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, neon-lit muscle car, glowing rims, purple fog, trending on artstation, unreal engine render, octane render, cinematic color grading",
      },
      {
        uid: "bg-004",
        name: "Cyberpunk Neon 04",
        negativePrompt: negativeDefault,
        scene:
          "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, aggressive supercar with neon underglow, rain reflections, trending on artstation, unreal engine render, octane render, cinematic color grading",
      },
      {
        uid: "bg-005",
        name: "Cyberpunk Neon 05",
        negativePrompt: negativeDefault,
        scene:
          "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, luxury hypercar glowing with neon lines, futuristic skyline, trending on artstation, unreal engine render, octane render, cinematic color grading",
      },
      {
        uid: "bg-006",
        name: "Cyberpunk Neon 06",
        negativePrompt: negativeDefault,
        scene:
          "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, sports car with electric lightning energy, neon glow, trending on artstation, unreal engine render, octane render, cinematic color grading",
      },
      {
        uid: "bg-007",
        name: "Cyberpunk Neon 07",
        negativePrompt: negativeDefault,
        scene:
          "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, futuristic car surrounded by plasma energy, trending on artstation, unreal engine render, octane render, cinematic color grading",
      },
      {
        uid: "bg-008",
        name: "Cyberpunk Neon 08",
        negativePrompt: negativeDefault,
        scene:
          "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, cyberpunk car with electricity flowing through body lines, trending on artstation, unreal engine render, octane render, cinematic color grading",
      },
      {
        uid: "bg-009",
        name: "Cyberpunk Neon 09",
        negativePrompt: negativeDefault,
        scene:
          "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, neon hypercar with energy waves and sparks, trending on artstation, unreal engine render, octane render, cinematic color grading",
      },
      {
        uid: "bg-010",
        name: "Cyberpunk Neon 10",
        negativePrompt: negativeDefault,
        scene:
          "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, car with glowing energy trails and motion blur, trending on artstation, unreal engine render, octane render, cinematic color grading",
      },
      {
        uid: "bg-011",
        name: "Cyberpunk Neon 11",
        negativePrompt: negativeDefault,
        scene:
          "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, supercar drifting with fire sparks, neon glow, smoke, trending on artstation, unreal engine render, octane render, cinematic color grading",
      },
      {
        uid: "bg-012",
        name: "Cyberpunk Neon 12",
        negativePrompt: negativeDefault,
        scene:
          "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, neon car surrounded by colored smoke, trending on artstation, unreal engine render, octane render, cinematic color grading",
      },
      {
        uid: "bg-013",
        name: "Cyberpunk Neon 13",
        negativePrompt: negativeDefault,
        scene:
          "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, aggressive car with flames and neon accents, trending on artstation, unreal engine render, octane render, cinematic color grading",
      },
      {
        uid: "bg-014",
        name: "Cyberpunk Neon 14",
        negativePrompt: negativeDefault,
        scene:
          "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, futuristic car emerging from smoke, trending on artstation, unreal engine render, octane render, cinematic color grading",
      },
      {
        uid: "bg-015",
        name: "Cyberpunk Neon 15",
        negativePrompt: negativeDefault,
        scene:
          "ultra realistic futuristic car, cyberpunk neon style, dark environment, night scene, strong neon lighting (purple, blue, pink), glowing light strips on car body, neon underglow, illuminated rims, wet reflective ground, cinematic lighting, high contrast, volumetric fog, smoke and light particles, energy effects (sparks, light streaks), sharp focus, 8k, ultra detailed, dramatic composition, low angle, depth of field, neon-lit car with fire embers and fog, trending on artstation, unreal engine render, octane render, cinematic color grading",
      },
    ];

    for (const p of promptRows) {
      await client.query(
        "insert into prompt_templates(uid, name, scene, negative_prompt, updated_at) values ($1,$2,$3,$4,$5) on conflict(uid) do nothing",
        [p.uid, p.name, p.scene, p.negativePrompt, updatedAt],
      );
    }

    await client.query(
      "insert into app_settings(key, value, updated_at) values ($1,$2,$3) on conflict(key) do update set value=excluded.value, updated_at=excluded.updated_at",
      ["seedBossPresetsDone", "1", updatedAt],
    );

    const structures: Array<{ uid: string; name: string; content: string }> = [
      {
        uid: "struct-1776779966347",
        name: "Tech House",
        content:
          "[Intro: kick + hi-hat groove, DJ friendly]\n[Groove: bassline enters, simple rhythm]\n[Build: add percussion layers]\n[Drop: full groove, catchy bassline hook]\n[Break: remove drums, filtered elements]\n[Build: reintroduce rhythm]\n[Drop: same groove with variation]\n[Outro: strip back for mixing]",
      },
      {
        uid: "struct-1776779935308",
        name: "TikTok",
        content:
          "[Hook Drop: immediate catchy drop, no intro, strong bass and melody]\n[Short Verse: minimal beat, quick vocal line]\n[Build-Up: fast riser, clap/snare build]\n[Drop: same hook repeated, slightly enhanced]\n[Break: very short pause or filtered section]\n[Drop: loopable, addictive, high energy]\n[Outro: quick ending]",
      },
      {
        uid: "struct-1776779918455",
        name: "POP EDM",
        content:
          "[Intro: soft piano or guitar, emotional vibe]\n[Verse: female vocal, intimate, minimal beat]\n[Pre-Chorus: build tension, add drums slowly]\n[Chorus: melodic drop with vocal hook, catchy and emotional]\n[Verse: variation, slightly fuller]\n[Pre-Chorus: rising energy]\n[Chorus: bigger drop, layered synths]\n[Bridge: emotional breakdown, minimal instruments]\n[Final Chorus: full energy, anthemic feel]\n[Outro: fade out with vocal]",
      },
      {
        uid: "struct-1776779899066",
        name: "Festival Big Drop (Suno Prompt Structure)",
        content:
          "[Intro: atmospheric pads, distant vocal chop, slow build]\n[Build-Up: risers, snare roll, tension increasing]\n[Drop: heavy big room kick, simple catchy lead melody, high energy]\n[Break: stripped back, emotional pad, vocal phrase]\n[Build-Up: stronger riser, faster snare roll, crowd hype]\n[Drop: bigger version, layered leads, more energy]\n[Outro: fade with pads and effects]",
      },
      { uid: "struct-1776779831633", name: "Main", content: "[Verse 1]\n[Chorus]\n[Verse 2]\n[Chorus]\n[Bridge]\n[Chorus]" },
    ];

    for (const s of structures) {
      await client.query(
        "insert into song_structures(uid, name, content, updated_at) values ($1,$2,$3,$4) on conflict(uid) do nothing",
        [s.uid, s.name, s.content, updatedAt],
      );
    }

    const descriptions: Array<{ uid: string; name: string; content: string }> = [
      {
        uid: "desc-1776780144364",
        name: "Party EDM",
        content:
          "A fun, high-energy EDM track at 142 BPM with a playful and danceable groove. Bright synths, catchy melodies, and a punchy kick drive the track, while the drop focuses on a simple, infectious rhythm that makes people want to move instantly. Designed for parties, clubs, and viral dance moments.",
      },
      {
        uid: "desc-1776780134746",
        name: "Cyberpunk Bass Track",
        content:
          "A futuristic EDM track at 142 BPM with a cyberpunk aesthetic. Featuring glitchy effects, robotic vocal textures, and a heavy, distorted bassline. The drop hits with sharp, syncopated rhythms and digital sound design, giving it a unique and edgy vibe that stands out and feels modern and experimental.",
      },
      {
        uid: "desc-1776780118348",
        name: "Emtional Melodic Rave",
        content:
          "An emotional yet powerful EDM track at 142 BPM combining soft piano elements with uplifting synth chords. The track builds from a heartfelt atmosphere into a euphoric drop with rich harmonies and strong sidechain energy. It balances emotional storytelling with festival-ready intensity, creating a goosebumps-inducing experience.",
      },
      {
        uid: "desc-1776780103602",
        name: "TikTok",
        content:
          "A catchy, upbeat EDM track at 142 BPM designed for instant virality. The song starts strong with a memorable hook and bouncy bassline, featuring a simple, addictive melody that loops perfectly for short-form content. Clean production, punchy drums, and a fun, energetic vibe make it ideal for dance trends and repeat listens.",
      },
      {
        uid: "desc-1776780090251",
        name: "Dark Festival Anthem",
        content:
          "A high-energy festival EDM track at 142 BPM with a dark, aggressive atmosphere. The song builds tension with cinematic pads and haunting vocal chants before exploding into a massive drop with punchy kicks, distorted bass, and a simple but powerful lead melody. Designed for mainstage crowds, with intense energy and a hard-hitting, unforgettable drop that feels epic and slightly ominous.",
      },
    ];

    for (const d of descriptions) {
      await client.query(
        "insert into song_descriptions(uid, name, content, updated_at) values ($1,$2,$3,$4) on conflict(uid) do nothing",
        [d.uid, d.name, d.content, updatedAt],
      );
    }

    await client.query("commit");
    return { ok: true as const };
  } catch (e) {
    await client.query("rollback").catch(() => undefined);
    throw e;
  } finally {
    await client.end();
  }
}

export async function bootstrapContent(cfg: DbCfg) {
  const [promptTemplates, structures, descriptions, textStyles, carModels] = await Promise.all([
    listPromptTemplates(cfg),
    listSongStructures(cfg),
    listSongDescriptions(cfg),
    listTextStyles(cfg),
    listCarModels(cfg),
  ]);
  return { promptTemplates, structures, descriptions, textStyles, carModels };
}
