import { describe, expect, it } from "vitest";
import type { ChannelProfile } from "../../src/features/dashboard/account-types";
import {
  buildPreferencesDraft,
  buildPreferencesPatch,
  buildProfileDraft,
  buildProfilePayload,
  buildPublicationDraft,
  buildPublicationPayload,
  deepEqual,
  filterProfiles,
  kindSourceSettings,
  parseCommaList,
  profileDraftDirty,
  profileInitials,
  renderTemplate,
  resolveKindSource,
  scheduleSummary,
  slugifyProfileFolder,
  splitPublishAt,
  validatePreferencesDraft,
  validateProfileDraft,
  validatePublicationDraft,
  workerLoadWarning,
  type PublicationDraft,
} from "../../src/features/settings/settings-types";

const profile = {
  id: "p1",
  user_id: "u1",
  name: "Beattok Remixes",
  folder_name: "beattok-remixes",
  run_prefix: "BR",
  logo_path: "uploads/logos/u1/p1-logo.png",
  video_template_id: null,
  reel_template_id: null,
  output_resolution: "1080x1920",
  image_config: { mode: "thumb_only", cover_paths: ["uploads/covers/u1/cover.png"] },
  youtube_config: {
    visibility: "scheduled",
    publish_at: "21:35",
    keywords: ["lofi", "night drive"],
    tags: "chill, focus",
    category: "10",
    description: "Late night mixes.",
    made_for_kids: false,
    ai_use: true,
    playlist: "PL123",
    title_template: "{title} (Official Audio)",
    description_template: "Mixed for {channel}",
  },
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
} satisfies ChannelProfile;

const second = {
  ...profile,
  id: "p2",
  name: "Deep Focus",
  folder_name: "deep-focus",
  run_prefix: "DF",
  youtube_config: {},
} satisfies ChannelProfile;

describe("settings profile helpers", () => {
  it("slugifies a profile name until the folder is edited", () => {
    expect(slugifyProfileFolder("Beattok Remixes")).toBe("beattok-remixes");
    expect(slugifyProfileFolder("  Night//Shift  ")).toBe("night-shift");
    expect(slugifyProfileFolder("***")).toBe("profile");

    const draft = buildProfileDraft(null);
    expect(draft.folderName).toBe("");
    expect(slugifyProfileFolder("Beattok Remixes")).not.toBe(draft.folderName);
  });

  it("builds a draft from a profile including media and modes", () => {
    const draft = buildProfileDraft(profile);
    expect(draft).toMatchObject({
      name: "Beattok Remixes",
      folderName: "beattok-remixes",
      runPrefix: "BR",
      outputResolution: "1080x1920",
      imageMode: "thumb_only",
      logoPath: "uploads/logos/u1/p1-logo.png",
      coverPath: "uploads/covers/u1/cover.png",
      logoBase64: null,
      coverBase64: null,
    });
    expect(buildProfileDraft({ ...profile, image_config: { mode: "nonsense" } }).imageMode).toBe("bg_thumb");
    expect(buildProfileDraft({ ...profile, output_resolution: "640x480" }).outputResolution).toBe("1920x1080");
  });

  it("builds the minimal profile payload the API merges", () => {
    const draft = buildProfileDraft(profile);
    expect(buildProfilePayload(draft)).toEqual({
      name: "Beattok Remixes",
      folder_name: "beattok-remixes",
      run_prefix: "BR",
      output_resolution: "1080x1920",
      image_config: { mode: "thumb_only" },
    });

    const withMedia = {
      ...draft,
      name: "  Night Shift  ",
      folderName: "",
      logoBase64: "logo-b64",
      coverBase64: "cover-b64",
    };
    expect(buildProfilePayload(withMedia)).toMatchObject({
      name: "Night Shift",
      folder_name: "night-shift",
      logo_base64: "logo-b64",
      cover_images: ["cover-b64"],
    });
  });

  it("validates the profile name, folder and run prefix", () => {
    const base = buildProfileDraft(profile);
    expect(validateProfileDraft(base, [profile, second], profile.id)).toEqual({});

    const noName = { ...base, name: "   " };
    expect(validateProfileDraft(noName, [profile], null).name).toBe("Enter a profile name.");

    const duplicate = { ...base, name: "deep focus" };
    expect(validateProfileDraft(duplicate, [profile, second], profile.id).name).toBe(
      "A profile with this name already exists.",
    );
    expect(validateProfileDraft(duplicate, [profile, second], second.id).name).toBeUndefined();

    const collision = { ...base, folderName: "deep-focus" };
    expect(validateProfileDraft(collision, [profile, second], profile.id).folderName).toContain(
      "already used by Deep Focus",
    );

    const unsafePrefix = { ...base, runPrefix: "a/b" };
    expect(validateProfileDraft(unsafePrefix, [profile], profile.id).runPrefix).toContain(
      "letters, numbers",
    );
    const unsafeFolder = { ...base, folderName: "a b" };
    expect(validateProfileDraft(unsafeFolder, [profile], profile.id).folderName).toContain(
      "letters, numbers",
    );
  });

  it("tracks dirty state by value, not identity", () => {
    const draft = buildProfileDraft(profile);
    expect(profileDraftDirty(draft, buildProfileDraft(profile))).toBe(false);
    expect(profileDraftDirty({ ...draft, runPrefix: "ZX" }, draft)).toBe(true);
    expect(deepEqual({ a: [1, 2] }, { a: [1, 2] })).toBe(true);
    expect(deepEqual({ a: [1, 2] }, { a: [2, 1] })).toBe(false);
  });

  it("searches by name, folder and run prefix", () => {
    const list = [profile, second];
    expect(filterProfiles(list, "deep").map((item) => item.id)).toEqual(["p2"]);
    expect(filterProfiles(list, "BR").map((item) => item.id)).toEqual(["p1"]);
    expect(filterProfiles(list, "beattok-rem").map((item) => item.id)).toEqual(["p1"]);
    expect(filterProfiles(list, "")).toHaveLength(2);
    expect(filterProfiles(list, "zzz")).toHaveLength(0);
    expect(profileInitials("Night Shift")).toBe("NS");
    expect(profileInitials("")).toBe("P");
  });
});

describe("settings publication helpers", () => {
  it("reads and writes the stored publication config", () => {
    const draft = buildPublicationDraft(profile);
    expect(draft).toMatchObject({
      description: "Late night mixes.",
      keywords: "lofi, night drive",
      tags: "chill, focus",
      visibility: "scheduled",
      publishHour: "21",
      publishMinute: "35",
      aiUse: true,
      madeForKids: false,
      category: "10",
      playlist: "PL123",
      titleTemplate: "{title} (Official Audio)",
      descriptionTemplate: "Mixed for {channel}",
    });

    const payload = buildPublicationPayload(draft, { extra: "kept" });
    expect(payload).toMatchObject({
      extra: "kept",
      visibility: "scheduled",
      publish_at: "21:35",
      keywords: ["lofi", "night drive"],
      tags: ["chill", "focus"],
      category: "10",
      playlist: "PL123",
      ai_use: true,
      made_for_kids: false,
    });

    const unscheduled = buildPublicationPayload({ ...draft, visibility: "unlisted" }, null);
    expect(unscheduled.publish_at).toBeNull();
  });

  it("carries the saved template ids without forcing them into youtube_config", () => {
    const draft = buildPublicationDraft({
      ...profile,
      video_template_id: "night-drive-long",
      reel_template_id: "night-drive-reel",
    });
    expect(draft.videoTemplateId).toBe("night-drive-long");
    expect(draft.reelTemplateId).toBe("night-drive-reel");
    const payload = buildPublicationPayload(draft, null);
    expect(payload).not.toHaveProperty("video_template_id");
    expect(payload).not.toHaveProperty("reel_template_id");
    const empty = buildPublicationDraft(profile);
    expect(empty.videoTemplateId).toBe("");
    expect(empty.reelTemplateId).toBe("");
  });

  it("rounds schedule minutes to five and ignores invalid values", () => {
    expect(splitPublishAt("21:37")).toEqual({ hour: "21", minute: "35" });
    expect(splitPublishAt("2026-11-20T07:05:00Z")).toEqual({ hour: "07", minute: "05" });
    expect(splitPublishAt("")).toEqual({ hour: "00", minute: "00" });
    expect(splitPublishAt("nonsense")).toEqual({ hour: "00", minute: "00" });
  });

  it("summarises a scheduled publish time only when scheduled", () => {
    const draft = buildPublicationDraft(profile);
    const now = new Date(2026, 10, 19, 9, 0, 0);
    expect(scheduleSummary({ ...draft, visibility: "public" }, now)).toBe("");
    const summary = scheduleSummary(draft, now);
    expect(summary.length).toBeGreaterThan(0);
    expect(summary).not.toBe(scheduleSummary({ ...draft, publishHour: "10" }, now));
  });

  it("validates schedule, keywords, tags and playlists", () => {
    const draft: PublicationDraft = buildPublicationDraft(profile);
    const context = {
      connected: true,
      playlistsLoaded: true,
      playlists: [{ id: "PL123" }, { id: "PL999" }],
    };
    expect(validatePublicationDraft(draft, context)).toEqual({});

    expect(
      validatePublicationDraft({ ...draft, publishMinute: "99" }, context).publishMinute,
    ).toContain("minute");
    expect(
      validatePublicationDraft({ ...draft, visibility: "public", publishMinute: "99" }, context),
    ).toEqual({});

    expect(
      validatePublicationDraft({ ...draft, keywords: "a".repeat(501) }, context).keywords,
    ).toContain("500");
    expect(
      validatePublicationDraft(
        { ...draft, tags: Array.from({ length: 16 }, (_, index) => `tag${index}`).join(", ") },
        context,
      ).tags,
    ).toContain("15");
    expect(
      validatePublicationDraft({ ...draft, playlist: "PL404" }, context).playlist,
    ).toContain("not on the channel");
    expect(
      validatePublicationDraft(
        { ...draft, playlist: "PL404" },
        { ...context, playlistsLoaded: false },
      ),
    ).toEqual({});
    expect(validatePublicationDraft({ ...draft, titleTemplate: "x".repeat(101) }, context).titleTemplate).toContain(
      "100",
    );
  });

  it("renders documented tokens and collapses whitespace", () => {
    expect(renderTemplate("{title} (Official Audio)", { title: "Neon Skyline" })).toBe(
      "Neon Skyline (Official Audio)",
    );
    expect(
      renderTemplate("  {album}  ·  {channel} ", { title: "Song", album: "Album", channel: "Night Shift" }),
    ).toBe("Album · Night Shift");
    expect(renderTemplate("", { title: "Song" })).toBe("");
    expect(parseCommaList(" one, two ,, three ")).toEqual(["one", "two", "three"]);
  });
});

describe("settings preferences helpers", () => {
  it("reads defaults and legacy keys", () => {
    const defaults = buildPreferencesDraft({});
    expect(defaults).toMatchObject({
      ffmpegPath: "",
      sunoOutputDir: "",
      musicWorkers: 1,
      imageWorkers: 4,
      exportWorkers: 1,
      mergeWorkers: 1,
      youtubeWorkers: 1,
      chunkSizeMb: 256,
      outputResolution: "1920x1080",
      styleStrength: 80,
      imageSourceMode: "ai",
      backgroundSource: "category",
      thumbnailSource: "category",
      thumbnailGeneration: "background_text",
    });

    const stored = buildPreferencesDraft({
      ffmpegPath: "C:\\tools\\ffmpeg.exe",
      sunoOutputDir: "D:\\Suno",
      perfMusicWorkers: 2,
      perfImageWorkers: 99,
      videoExportWorkers: 3,
      perfMergeWorkers: 7,
      perfYouTubeWorkers: 4,
      youtubeUploadChunkSizeMb: 999,
      outputResolution: "1080x1920",
      styleStrength: 120,
      imageSourceMode: "manual",
      backgroundSourceMode: "prompt",
      imageThumbnailSourceMode: "category",
      imageThumbnailPromptSource: "admin_library",
      thumbnailReferenceMode: "composite",
    });
    expect(stored).toMatchObject({
      ffmpegPath: "C:\\tools\\ffmpeg.exe",
      sunoOutputDir: "D:\\Suno",
      musicWorkers: 2,
      imageWorkers: 8,
      exportWorkers: 3,
      mergeWorkers: 2,
      youtubeWorkers: 4,
      chunkSizeMb: 256,
      outputResolution: "1080x1920",
      styleStrength: 100,
      imageSourceMode: "manual",
      backgroundSource: "prompt_only",
      thumbnailSource: "admin_library",
      thumbnailGeneration: "composite",
    });

    const locked = buildPreferencesDraft({
      imagePromptLibraryOnly: true,
      imageBackgroundSourceMode: "category",
      imageThumbnailSourceMode: "prompt_only",
    });
    expect(locked.backgroundSource).toBe("admin_library");
    expect(locked.thumbnailSource).toBe("admin_library");
  });

  it("maps combined background/thumbnail sources", () => {
    expect(resolveKindSource("prompt_only", "custom")).toBe("prompt_only");
    expect(resolveKindSource("category", "custom")).toBe("category");
    expect(resolveKindSource("category", "admin_library")).toBe("admin_library");
    expect(kindSourceSettings("admin_library")).toEqual({
      mode: "prompt_only",
      promptSource: "admin_library",
    });
    expect(kindSourceSettings("prompt_only")).toEqual({ mode: "prompt_only", promptSource: "custom" });
    expect(kindSourceSettings("category")).toEqual({ mode: "category", promptSource: "custom" });
  });

  it("builds a minimal patch with the paired settings keys", () => {
    const baseline = buildPreferencesDraft({});
    const emptyPatch = buildPreferencesPatch(baseline, baseline);
    expect(emptyPatch).toEqual({});

    const patch = buildPreferencesPatch(
      {
        ...baseline,
        sunoOutputDir: "  D:\\Music  ",
        imageWorkers: 6,
        exportWorkers: 4,
        outputResolution: "1080x1080",
        backgroundSource: "admin_library",
        thumbnailGeneration: "composite",
        styleStrength: 60,
      },
      baseline,
    );
    expect(patch).toEqual({
      sunoOutputDir: "D:\\Music",
      perfImageWorkers: 6,
      perfExportWorkers: 4,
      videoExportWorkers: 4,
      outputResolution: "1080x1080",
      imageResolution: "1080x1080",
      styleStrength: 60,
      imageBackgroundSourceMode: "prompt_only",
      imageBackgroundPromptSource: "admin_library",
      thumbnailReferenceMode: "composite",
    });
  });

  it("validates worker bounds, chunks and the load guardrail", () => {
    const draft = buildPreferencesDraft({});
    expect(validatePreferencesDraft(draft)).toEqual({});
    const errors = validatePreferencesDraft({
      ...draft,
      musicWorkers: 9,
      imageWorkers: 0,
      mergeWorkers: 3,
      chunkSizeMb: 64,
      styleStrength: 101,
    });
    expect(errors.musicWorkers).toContain("1 and 5");
    expect(errors.imageWorkers).toContain("1 and 8");
    expect(errors.mergeWorkers).toContain("1 and 2");
    expect(errors.chunkSizeMb).toContain("128");
    expect(errors.styleStrength).toContain("0 and 100");
    expect(workerLoadWarning(draft)).toBeNull();
    expect(
      workerLoadWarning({ ...draft, musicWorkers: 5, imageWorkers: 8, exportWorkers: 10 }),
    ).toContain("Total worker count is 25");
  });
});
