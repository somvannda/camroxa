import { describe, expect, it } from "vitest";
import {
  SETTINGS_TABS,
  SUNO_VERSION_OPTIONS,
  buildPromptDefaultsDraft,
  buildPromptDefaultsPatch,
  buildPromptEditorDraft,
  buildSunoSettingsDraft,
  buildSunoSettingsPatch,
  buildUserPromptPayload,
  canPoolNext,
  canPoolPrevious,
  clampPoolOffset,
  countDirtyTabs,
  emptyPromptDefaultsDraft,
  emptyPromptEditorDraft,
  filterPromptOptions,
  isSupportedSunoVersion,
  normalizePoolItems,
  normalizePoolStats,
  normalizePromptOptions,
  normalizeUserPrompts,
  paginatePromptOptions,
  poolOffsetForPage,
  poolPageCount,
  poolPageLabel,
  poolRangeLabel,
  promptDefaultsDirtyFor,
  promptEditorDraftDirty,
  promptOptionLabel,
  removeUserPrompt,
  sunoSettingsDirty,
  upsertUserPrompt,
  validatePromptEditorDraft,
  validateSunoSettingsDraft,
  type PromptDefaultsDraft,
  type SunoSettingsDraft,
  type UserPromptEntry,
} from "../../src/features/settings/settings-types";

const userEntry = (overrides: Partial<UserPromptEntry> = {}): UserPromptEntry => ({
  id: "prompt-1",
  name: "Late night",
  content: "Warm analog synths.",
  updatedAt: "2026-11-01T00:00:00Z",
  ...overrides,
});

describe("settings tab order", () => {
  it("lists all eight tabs in the save-all order", () => {
    expect(SETTINGS_TABS.map((tab) => tab.id)).toEqual([
      "profiles",
      "publication",
      "preferences",
      "descriptions",
      "structures",
      "moods",
      "pools",
      "suno",
    ]);
  });

  it("counts only the dirty tabs", () => {
    expect(
      countDirtyTabs({
        profiles: false,
        publication: false,
        preferences: true,
        descriptions: true,
        structures: false,
        moods: false,
        pools: false,
        suno: true,
      }),
    ).toBe(3);
  });
});

describe("prompt workspace defaults", () => {
  it("reads only the stored default ids", () => {
    expect(
      buildPromptDefaultsDraft({
        defaultDescriptionId: "d1",
        defaultStructureId: "s1",
        defaultMoodId: "m1",
        sunoTimeoutMs: 90000,
      }),
    ).toEqual({ descriptionId: "d1", structureId: "s1", moodId: "m1" });
    expect(buildPromptDefaultsDraft(null)).toEqual(emptyPromptDefaultsDraft());
    expect(buildPromptDefaultsDraft({ defaultDescriptionId: 42 })).toEqual({
      descriptionId: "",
      structureId: "",
      moodId: "",
    });
  });

  it("patches only the changed keys", () => {
    const baseline: PromptDefaultsDraft = { descriptionId: "d1", structureId: "s1", moodId: "m1" };
    expect(buildPromptDefaultsPatch(baseline, baseline)).toEqual({});
    expect(
      buildPromptDefaultsPatch(
        { descriptionId: " d2 ", structureId: "s1", moodId: "" },
        baseline,
      ),
    ).toEqual({ defaultDescriptionId: "d2", defaultMoodId: "" });
  });

  it("assigns the paired structure to the structures tab", () => {
    const baseline: PromptDefaultsDraft = { descriptionId: "d1", structureId: "s1", moodId: "m1" };
    const draft: PromptDefaultsDraft = { descriptionId: "d2", structureId: "s2", moodId: "m2" };

    expect(promptDefaultsDirtyFor("descriptions", draft, baseline)).toBe(true);
    expect(promptDefaultsDirtyFor("descriptions", { ...baseline, structureId: "s2" }, baseline)).toBe(
      false,
    );
    expect(promptDefaultsDirtyFor("structures", { ...baseline, descriptionId: "d2" }, baseline)).toBe(false);
    expect(promptDefaultsDirtyFor("structures", { ...baseline, structureId: "s2" }, baseline)).toBe(true);
    expect(promptDefaultsDirtyFor("moods", { ...baseline, descriptionId: "d2" }, baseline)).toBe(false);
    expect(promptDefaultsDirtyFor("moods", { ...baseline, moodId: "m2" }, baseline)).toBe(true);
  });
});

describe("prompt catalog options", () => {
  const options = normalizePromptOptions([
    { id: "b", name: "Bedroom pop", is_owned: true },
    { id: "a", name: "Ambient", is_owned: false, match_key: " ambient " },
    { id: "", name: "Broken" },
    { id: "c", name: "  ", is_owned: false },
  ]);

  it("drops entries without an id and keeps ownership", () => {
    expect(options).toEqual([
      { id: "b", name: "Bedroom pop", owned: true, matchKey: null },
      { id: "a", name: "Ambient", owned: false, matchKey: "ambient" },
      { id: "c", name: "c", owned: false, matchKey: null },
    ]);
    expect(normalizePromptOptions({ not: "a list" })).toEqual([]);
  });

  it("filters by name or id, case-insensitively, sorted", () => {
    expect(filterPromptOptions(options, "").map((option) => option.id)).toEqual(["a", "b", "c"]);
    expect(filterPromptOptions(options, "BE").map((option) => option.id)).toEqual(["b"]);
    expect(filterPromptOptions(options, "a").map((option) => option.id)).toEqual(["a"]);
    expect(filterPromptOptions(options, "zzz")).toEqual([]);
    expect(promptOptionLabel(options[0])).toBe("Bedroom pop · Yours");
    expect(promptOptionLabel(options[1])).toBe("Ambient · Camxora");
  });

  it("paginates and clamps the page", () => {
    const many = Array.from({ length: 19 }, (_, index) => ({
      id: `p${index}`,
      name: `Prompt ${index}`,
      owned: true,
      matchKey: null,
    }));
    const first = paginatePromptOptions(many, 0, 8);
    expect(first.items).toHaveLength(8);
    expect(first.pageCount).toBe(3);
    expect(paginatePromptOptions(many, 2, 8).items).toHaveLength(3);
    expect(paginatePromptOptions(many, 99, 8).page).toBe(2);
    expect(paginatePromptOptions([], 4, 8)).toMatchObject({ items: [], pageCount: 1, page: 0 });
  });
});

describe("user prompt editor", () => {
  it("builds a draft and trims the payload", () => {
    expect(buildPromptEditorDraft(userEntry())).toEqual({
      id: "prompt-1",
      name: "Late night",
      content: "Warm analog synths.",
    });
    expect(buildPromptEditorDraft(null)).toEqual(emptyPromptEditorDraft());
    expect(
      buildUserPromptPayload({ id: null, name: "  New name  ", content: "  body  " }),
    ).toEqual({ name: "New name", content: "body" });
  });

  it("tracks dirty state by value", () => {
    const draft = buildPromptEditorDraft(userEntry());
    expect(promptEditorDraftDirty(draft, buildPromptEditorDraft(userEntry()))).toBe(false);
    expect(promptEditorDraftDirty({ ...draft, name: "Other" }, draft)).toBe(true);
  });

  it("validates name, content and duplicate names", () => {
    const base = { id: null, name: "New", content: "Body" };
    expect(validatePromptEditorDraft(base, [userEntry()])).toEqual({});

    expect(validatePromptEditorDraft({ ...base, name: "   " }, []).name).toBe("Enter a name.");
    expect(validatePromptEditorDraft({ ...base, name: "x".repeat(101) }, []).name).toContain("100");
    expect(validatePromptEditorDraft({ ...base, content: "   " }, []).content).toBe("Enter the prompt text.");
    expect(validatePromptEditorDraft({ ...base, content: "x".repeat(5001) }, []).content).toContain("5000");

    expect(validatePromptEditorDraft({ ...base, name: "late NIGHT" }, [userEntry()]).name).toContain(
      "already have",
    );
    expect(
      validatePromptEditorDraft({ ...base, id: "prompt-1", name: "Late night" }, [userEntry()]),
    ).toEqual({});
  });

  it("upserts and removes catalog entries by id", () => {
    const list = [userEntry({ id: "a", name: "Alpha" }), userEntry({ id: "b", name: "Beta" })];
    const created = upsertUserPrompt(list, userEntry({ id: "c", name: "Charlie" }));
    expect(created.map((entry) => entry.id)).toEqual(["a", "b", "c"]);
    const edited = upsertUserPrompt(created, userEntry({ id: "b", name: "Beta edited" }));
    expect(edited).toHaveLength(3);
    expect(edited.find((entry) => entry.id === "b")?.name).toBe("Beta edited");
    expect(removeUserPrompt(edited, "b").map((entry) => entry.id)).toEqual(["a", "c"]);
  });

  it("normalises user prompt lists", () => {
    expect(
      normalizeUserPrompts([
        { id: "a", name: "A", content: "body", updated_at: "2026-01-01T00:00:00Z" },
        { id: "", name: "Broken" },
        "nope",
      ]),
    ).toEqual([{ id: "a", name: "A", content: "body", updatedAt: "2026-01-01T00:00:00Z" }]);
    expect(normalizeUserPrompts(null)).toEqual([]);
  });
});

describe("content pool helpers", () => {
  it("normalises stats and rows", () => {
    expect(
      normalizePoolStats({
        openings: { total: 12, unused: 9 },
        titles: { total: "4", unused: "0" },
        albums: {},
      }),
    ).toEqual({
      openings: { total: 12, unused: 9 },
      titles: { total: 4, unused: 0 },
      albums: { total: 0, unused: 0 },
    });
    expect(normalizePoolStats(null).titles).toEqual({ total: 0, unused: 0 });

    expect(
      normalizePoolItems([
        { id: 2, text: "Second", used_count: 3, created_at: "2026-01-02T00:00:00Z" },
        { id: 1, text: "First", secondary_text: " line two ", used_count: "0" },
        { id: 0, text: "Broken" },
      ]),
    ).toEqual([
      { id: 2, text: "Second", secondaryText: null, usedCount: 3, createdAt: "2026-01-02T00:00:00Z" },
      { id: 1, text: "First", secondaryText: " line two ", usedCount: 0, createdAt: null },
    ]);
  });

  it("computes page bounds and labels", () => {
    expect(poolPageCount(0)).toBe(1);
    expect(poolPageCount(50)).toBe(1);
    expect(poolPageCount(51)).toBe(2);
    expect(poolOffsetForPage(2)).toBe(100);
    expect(clampPoolOffset(500, 120)).toBe(100);
    expect(clampPoolOffset(-10, 120)).toBe(0);
    expect(canPoolPrevious(0)).toBe(false);
    expect(canPoolPrevious(50)).toBe(true);
    expect(canPoolNext(120, 0)).toBe(true);
    expect(canPoolNext(120, 100)).toBe(false);
    expect(canPoolNext(0, 0)).toBe(false);
    expect(poolRangeLabel(120, 0)).toBe("1–50 of 120");
    expect(poolRangeLabel(120, 100)).toBe("101–120 of 120");
    expect(poolRangeLabel(0, 0)).toBe("0 items");
    expect(poolPageLabel(120, 50)).toBe("Page 2 of 3");
  });
});

describe("Suno defaults", () => {
  const stored = {
    sunoDefaultVersion: "v5.5",
    sunoMergeEnabled: true,
    sunoMergeGroupSize: 3,
    sunoTimeoutMs: 120000,
    sunoRetryCount: 5,
    unknownKey: "keep me",
  };

  it("reads defaults with clamping and legacy fallbacks", () => {
    expect(buildSunoSettingsDraft(stored)).toEqual({
      defaultVersion: "v5.5",
      mergeEnabled: true,
      mergeGroupSize: 3,
      timeoutMs: 120000,
      retryCount: 5,
    });
    expect(buildSunoSettingsDraft(null)).toEqual({
      defaultVersion: "v6",
      mergeEnabled: false,
      mergeGroupSize: 0,
      timeoutMs: 90000,
      retryCount: 3,
    });
    expect(
      buildSunoSettingsDraft({ sunoTimeoutMs: 10, sunoMergeGroupSize: 99, sunoRetryCount: -2 }),
    ).toMatchObject({ timeoutMs: 1000, mergeGroupSize: 20, retryCount: 0 });
  });

  it("patches only changed keys and preserves unknown ones", () => {
    const baseline = buildSunoSettingsDraft(stored);
    expect(buildSunoSettingsPatch(baseline, stored)).toEqual({});
    expect(sunoSettingsDirty(baseline, buildSunoSettingsDraft(stored))).toBe(false);

    const patch = buildSunoSettingsPatch(
      {
        ...baseline,
        defaultVersion: "v6",
        mergeEnabled: false,
        mergeGroupSize: 4,
        timeoutMs: 150000,
        retryCount: 2,
      },
      stored,
    );
    expect(patch).toEqual({
      sunoDefaultVersion: "v6",
      sunoMergeEnabled: false,
      sunoMergeGroupSize: 4,
      sunoTimeoutMs: 150000,
      sunoRetryCount: 2,
    });
    expect(patch).not.toHaveProperty("unknownKey");
    expect(sunoSettingsDirty({ ...baseline, mergeGroupSize: 4 }, baseline)).toBe(true);
  });

  it("validates versions and numeric bounds", () => {
    const valid: SunoSettingsDraft = {
      defaultVersion: "v6",
      mergeEnabled: false,
      mergeGroupSize: 0,
      timeoutMs: 90000,
      retryCount: 3,
    };
    expect(validateSunoSettingsDraft(valid)).toEqual({});
    expect(SUNO_VERSION_OPTIONS).toContain("v6 mini");
    expect(isSupportedSunoVersion("v5")).toBe(true);
    expect(isSupportedSunoVersion("v4")).toBe(false);

    const errors = validateSunoSettingsDraft({
      defaultVersion: "v4",
      mergeEnabled: true,
      mergeGroupSize: 21,
      timeoutMs: 999,
      retryCount: 21,
    });
    expect(errors.defaultVersion).toContain("not supported");
    expect(errors.mergeGroupSize).toContain("0 and 20");
    expect(errors.timeoutMs).toContain("1000");
    expect(errors.retryCount).toContain("0 and 20");
    expect(validateSunoSettingsDraft({ ...valid, timeoutMs: 0 }).timeoutMs).toContain("1000");
    expect(validateSunoSettingsDraft({ ...valid, retryCount: -1 }).retryCount).toContain("0 and 20");
    expect(validateSunoSettingsDraft({ ...valid, mergeGroupSize: 2.5 }).mergeGroupSize).toContain(
      "0 and 20",
    );
  });
});
