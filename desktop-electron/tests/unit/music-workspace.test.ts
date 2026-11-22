import { describe, expect, it } from "vitest";
import {
  batchStatusText,
  buildDraftDescription,
  buildHistoryAvoidLists,
  createBatchesSummary,
  effectPreview,
  flattenHistory,
  historySummary,
  inclusiveDateList,
  inclusiveDaySpan,
  matchesHistoryDateRange,
  planManualRunDirectories,
  plannedDaysText,
  toggleSelection,
  validatePairs,
  songFolder,
} from "../../src/features/music/music-format";
import {
  buildMusicSettings,
  DEFAULT_MUSIC_SETTINGS,
  imageSourceMode,
  manualOutputBase,
  musicSettingsPatch,
  musicSettingsSnapshot,
} from "../../src/features/music/music-settings";
import type { MusicHistoryBatch } from "../../src/features/music/music-types";

const batch = (overrides: Partial<MusicHistoryBatch> = {}): MusicHistoryBatch => ({
  batch_id: "batch-1",
  from_date: "2026-11-18",
  to_date: "2026-11-18",
  created_at: "2026-11-18T10:00:00Z",
  ok_profile_name: "Night Shift",
  alt_profile_name: "Deep Focus",
  songs: [
    {
      song_id: "song-1",
      batch_index: 0,
      title: "First Light",
      album: "Night Album",
      lyrics: "[verse]\nOpening line\nSecond line",
      description_id: "desc-1",
      description_name: "Bedroom pop",
      structure_id: "struct-1",
      structure_name: "Verse chorus",
      output_dir_ok: "C:\\Runs\\Night\\2026-11-18",
      output_dir_alt: "",
      status: "completed",
      suno_status: "completed",
      created_at: "2026-11-18T10:05:00Z",
    },
  ],
  ...overrides,
});

describe("music date range", () => {
  it("computes inclusive spans and date lists", () => {
    expect(inclusiveDaySpan("2026-11-19", "2026-11-19")).toBe(1);
    expect(inclusiveDaySpan("2026-11-17", "2026-11-19")).toBe(3);
    expect(inclusiveDaySpan("2026-11-19", "2026-11-18")).toBeNull();
    expect(inclusiveDaySpan("", "2026-11-19")).toBeNull();
    expect(inclusiveDateList("2026-11-17", "2026-11-19")).toEqual([
      "2026-11-17",
      "2026-11-18",
      "2026-11-19",
    ]);
  });

  it("labels the planned-day chip and invalid range", () => {
    expect(plannedDaysText("2026-11-19", "2026-11-19")).toBe("1 planned day");
    expect(plannedDaysText("2026-11-17", "2026-11-19")).toBe("3 planned days");
    expect(plannedDaysText("2026-11-19", "2026-11-18")).toBe(
      "Choose a valid inclusive date range.",
    );
  });
});

describe("music effect preview", () => {
  it("maps creativity to the documented effect values", () => {
    expect(effectPreview(55)).toEqual({
      valence: 59,
      danceability: 56,
      instrumentalness: 40,
    });
    expect(effectPreview(0)).toEqual({
      valence: 20,
      danceability: 15,
      instrumentalness: 10,
    });
    expect(effectPreview(100)).toEqual({
      valence: 90,
      danceability: 90,
      instrumentalness: 65,
    });
  });
});

describe("draft avoid lists and seeds", () => {
  it("uses the newest history window slice", () => {
    const batches = Array.from({ length: 8 }, (_, index) =>
      batch({
        batch_id: `batch-${index}`,
        songs: [
          {
            song_id: `song-${index}`,
            batch_index: 0,
            title: `Title ${index}`,
            album: `Album ${index}`,
            lyrics: `Opening ${index}`,
          },
        ],
      }),
    );
    const avoid = buildHistoryAvoidLists(batches, 50);
    expect(avoid.titles).toHaveLength(5);
    expect(avoid.titles).toContain("Title 0");
    expect(avoid.titles).not.toContain("Title 5");
    expect(avoid.albums[0]).toBe("Album 0");
    expect(avoid.openings[0]).toBe("Opening 0");
    expect(buildHistoryAvoidLists([], 50)).toEqual({ titles: [], albums: [], openings: [] });
  });

  it("adds the inspiration suffix only when seeds exist", () => {
    expect(buildDraftDescription("Night drive", null)).toBe("Night drive");
    expect(
      buildDraftDescription("Night drive", {
        titleSeed: "Neon Road",
        albumSeed: "After Hours",
        openingSeed: "The city hums",
      }),
    ).toBe("Night drive\n\nInspiration (do not copy words): Neon Road / After Hours");
  });
});

describe("channel pairs", () => {
  it("toggles while preserving order", () => {
    expect(toggleSelection([], "a")).toEqual(["a"]);
    expect(toggleSelection(["a", "b"], "a")).toEqual(["b"]);
    expect(toggleSelection(["a", "b"], "c")).toEqual(["a", "b", "c"]);
  });

  it("flags overlap and mismatched counts", () => {
    expect(validatePairs(["a"], ["a"])).toMatchObject({ overlap: true, canPair: false });
    expect(validatePairs(["a", "b"], ["c"])).toMatchObject({
      mismatch: true,
      canPair: false,
    });
    expect(validatePairs(["a"], ["b"])).toMatchObject({ canPair: true });
    expect(validatePairs([], [])).toMatchObject({ canPair: false });
  });
});

describe("history flattening", () => {
  it("filters by date overlap and last batch only", () => {
    const newer = batch({ batch_id: "new" });
    const older = batch({
      batch_id: "old",
      from_date: "2026-11-01",
      to_date: "2026-11-01",
      created_at: "2026-11-01T10:00:00Z",
    });
    const rows = flattenHistory([newer, older], {
      fromDate: "2026-11-18",
      toDate: "2026-11-18",
      lastBatchOnly: false,
    });
    expect(rows.map((row) => row.batch.batch_id)).toEqual(["new"]);

    const lastOnly = flattenHistory([newer, older], {
      fromDate: "",
      toDate: "",
      lastBatchOnly: true,
    });
    expect(lastOnly).toHaveLength(1);
    expect(lastOnly[0].batch.batch_id).toBe("new");
    expect(lastOnly[0].rowNumber).toBe(1);
    expect(lastOnly[0].batchIndex).toBe(0);
  });

  it("matches created dates when planned dates are missing", () => {
    const missing = batch({ from_date: null, to_date: null });
    expect(matchesHistoryDateRange(missing, "2026-11-18", "2026-11-18")).toBe(true);
    expect(matchesHistoryDateRange(missing, "2026-11-19", "2026-11-19")).toBe(false);
  });

  it("summarises filtered and unfiltered history", () => {
    const batches = [batch()];
    expect(historySummary(batches, flattenHistory(batches, {
      fromDate: "",
      toDate: "",
      lastBatchOnly: false,
    }), "1 batch · 1 song")).toBe("1 batch · 1 song");
    const filtered = flattenHistory(batches, {
      fromDate: "2026-11-19",
      toDate: "2026-11-19",
      lastBatchOnly: false,
    });
    expect(historySummary(batches, filtered)).toBe("0 batches · 0 songs shown (of 1 loaded)");
    expect(historySummary([], [])).toBe("");
  });

  it("exposes the folder path for each side", () => {
    const row = flattenHistory([batch()], {
      fromDate: "",
      toDate: "",
      lastBatchOnly: false,
    })[0];
    expect(songFolder(row.song, "primary")).toBe("C:\\Runs\\Night\\2026-11-18");
    expect(songFolder(row.song, "secondary")).toBe("");
  });
});

describe("manual run directories", () => {
  it("plans deterministic OK and ALT folders", () => {
    const plan = planManualRunDirectories({
      baseDir: "C:\\Runs\\",
      okProfileFolder: "Night Shift",
      altProfileFolder: "Deep/Focus",
      runLabel: "2026-11-19",
    });
    expect(plan.runFolderName).toBe("2026-11-19");
    expect(plan.okRunDir).toBe("C:\\Runs\\Night Shift\\2026-11-19");
    expect(plan.altRunDir).toBe("C:\\Runs\\Deep-Focus\\2026-11-19");
    expect(
      planManualRunDirectories({
        baseDir: "",
        okProfileFolder: "a",
        altProfileFolder: "b",
        runLabel: "2026-11-19",
      }),
    ).toEqual({ okRunDir: "", altRunDir: "", runFolderName: "" });
  });
});

describe("settings mapping", () => {
  it("applies API values and clamps out-of-range ones", () => {
    const settings = buildMusicSettings({
      language: "KM",
      creativity: 140,
      strictLevel: 0,
      uniquenessHistoryWindow: 10,
      defaultSongCount: 99,
      lyricsPolishStrength: -5,
      autoGSuno: true,
      autoUploadYouTube: true,
      defaultDescriptionId: "desc-1",
    });
    expect(settings.language).toBe("km");
    expect(settings.creativity).toBe(100);
    expect(settings.strictLevel).toBe(1);
    expect(settings.historyWindow).toBe(50);
    expect(settings.songCount).toBe(50);
    expect(settings.polishStrength).toBe(0);
    expect(settings.autoGSuno).toBe(true);
    expect(settings.autoUploadYouTube).toBe(true);
  });

  it("round-trips the PATCH keys and detects no-change snapshots", () => {
    const settings = buildMusicSettings({
      language: "fr",
      creativity: 40,
      defaultSongCount: 6,
      autoGenImage: true,
      primaryProfileIds: ["p1", "p2"],
      secondaryProfileIds: '["p3"]',
    });
    const patch = musicSettingsPatch(settings);
    expect(patch).toMatchObject({
      language: "fr",
      creativity: 40,
      defaultSongCount: 6,
      autoGenImage: true,
      lyricsPolishStrength: DEFAULT_MUSIC_SETTINGS.polishStrength,
      primaryProfileIds: ["p1", "p2"],
      secondaryProfileIds: ["p3"],
    });
    const snapshot = musicSettingsSnapshot(settings);
    expect(musicSettingsSnapshot({ ...settings })).toBe(snapshot);
    expect(musicSettingsSnapshot({ ...settings, creativity: 41 })).not.toBe(snapshot);
  });

  it("reads image mode and the manual base directory", () => {
    expect(imageSourceMode({ imageSourceMode: "manual" })).toBe("manual");
    expect(imageSourceMode({})).toBe("ai");
    expect(manualOutputBase({ sunoOutputDir: "C:\\Suno", downloadsDir: "C:\\Down" })).toBe(
      "C:\\Suno",
    );
    expect(manualOutputBase({ downloadsDir: "C:\\Down" })).toBe("C:\\Down");
    expect(manualOutputBase(null)).toBe("");
  });
});

describe("batch summaries", () => {
  it("reports the exact fan-out summary", () => {
    expect(
      createBatchesSummary({
        planned: 3,
        dayCount: 3,
        pairCount: 1,
        created: [
          { date: "2026-11-17", okName: "A", altName: "B" },
          { date: "2026-11-18", okName: "A", altName: "B" },
          { date: "2026-11-19", okName: "A", altName: "B" },
        ],
        failed: [],
      }),
    ).toBe("Created 3 batch runs across 3 planned days and 1 channel pair.");
  });

  it("keeps completed batches and names the missing slots on partial failure", () => {
    expect(
      createBatchesSummary({
        planned: 2,
        dayCount: 2,
        pairCount: 1,
        created: [{ date: "2026-11-18", okName: "A", altName: "B" }],
        failed: [
          {
            date: "2026-11-19",
            okName: "A",
            altName: "B",
            message: "Server error",
          },
        ],
      }),
    ).toBe(
      "Created 1 batch run across 2 planned days and 1 channel pair. Still missing: 2026-11-19 · A ↔ B.",
    );
  });

  it("formats polled batch status", () => {
    expect(
      batchStatusText({
        status: "drafting",
        drafts_completed: 2,
        total_songs: 4,
        suno_submitted: 0,
        suno_completed: 0,
        suno_failed: 0,
      }),
    ).toBe("drafting · 2/4 drafts");
  });
});
