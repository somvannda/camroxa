import { describe, expect, it } from "vitest";
import { buildMusicPipelinePlan, songIsReady } from "../../src/features/music/music-pipeline";
import type {
  ChannelProfile,
  MusicHistoryBatch,
  MusicHistorySong,
} from "../../src/features/music/music-types";

const profiles: ChannelProfile[] = [
  {
    id: "profile-ok",
    name: "Night Shift",
    video_template_id: "night-drive",
    reel_template_id: "night-drive-reel",
  },
  { id: "profile-alt", name: "Dawn Shift", video_template_id: "dawn-drive", reel_template_id: null },
];

function song(overrides: Partial<MusicHistorySong> = {}): MusicHistorySong {
  return {
    song_id: "song-1",
    batch_index: 0,
    title: "Neon Skyline",
    album: "Night Drive",
    output_dir_ok: "C:/runs/night",
    output_dir_alt: "C:/runs/dawn",
    downloaded_ok: true,
    downloaded_alt: true,
    ...overrides,
  };
}

function batch(overrides: Partial<MusicHistoryBatch> = {}): MusicHistoryBatch {
  return {
    batch_id: "batch-42",
    ok_profile_id: "profile-ok",
    alt_profile_id: "profile-alt",
    songs: [song()],
    ...overrides,
  };
}

describe("music pipeline plan", () => {
  it("reports an honest empty state when no batch finished", () => {
    const plan = buildMusicPipelinePlan({
      profiles,
      primaryIds: [],
      batches: [],
      videoTemplateId: "",
      reelTemplateId: "",
      merge: false,
      reel: false,
    });
    expect(plan.request).toBeNull();
    expect(plan.jobCount).toBe(0);
    expect(plan.message).toMatch(/no finished batch/i);
  });

  it("queues one long job per channel pair with the profile templates", () => {
    const plan = buildMusicPipelinePlan({
      profiles,
      primaryIds: [],
      batches: [batch()],
      videoTemplateId: "",
      reelTemplateId: "",
      merge: true,
      reel: false,
    });
    expect(plan.templateErrors).toEqual([]);
    expect(plan.request).not.toBeNull();
    const request = plan.request!;
    expect(request.batchId).toBe("batch-42");
    expect(request.merge).toBe(true);
    expect(request.outputDir).toBe("C:/runs/night");
    expect(request.jobs.map((job) => job.templateId).sort()).toEqual(["dawn-drive", "night-drive"]);
    expect(request.jobs.every((job) => job.branch === "long")).toBe(true);
    expect(plan.songCount).toBe(1);
  });

  it("adds a separate reel job per song when Auto-Reel is on", () => {
    const plan = buildMusicPipelinePlan({
      profiles,
      primaryIds: [],
      batches: [batch()],
      videoTemplateId: "",
      reelTemplateId: "",
      merge: false,
      reel: true,
    });
    const reels = plan.request!.jobs.filter((job) => job.branch === "reel");
    // Only the OK profile has a reel template.
    expect(reels).toHaveLength(1);
    expect(reels[0].templateId).toBe("night-drive-reel");
    expect(plan.templateErrors[0]).toMatch(/no reel template/i);
  });

  it("never queues a job without a template, and says which profile is missing one", () => {
    const plan = buildMusicPipelinePlan({
      profiles: [{ id: "profile-ok", name: "Night Shift" }],
      primaryIds: [],
      batches: [batch()],
      videoTemplateId: "",
      reelTemplateId: "",
      merge: false,
      reel: false,
    });
    expect(plan.request).toBeNull();
    expect(plan.templateErrors[0]).toMatch(/Night Shift/);
    expect(plan.templateErrors[0]).toMatch(/Settings/);
  });

  it("skips songs without a recorded run folder", () => {
    const plan = buildMusicPipelinePlan({
      profiles,
      primaryIds: [],
      batches: [
        batch({
          songs: [song({ title: "Missing", output_dir_ok: "", output_dir_alt: "", downloaded_ok: false })],
        }),
      ],
      videoTemplateId: "",
      reelTemplateId: "",
      merge: false,
      reel: false,
    });
    expect(plan.request).toBeNull();
    expect(plan.message).toMatch(/no songs are ready/i);
  });

  it("only queues the newest batch with ready songs", () => {
    const plan = buildMusicPipelinePlan({
      profiles,
      primaryIds: [],
      batches: [batch({ batch_id: "newer" }), batch({ batch_id: "older" })],
      videoTemplateId: "",
      reelTemplateId: "",
      merge: false,
      reel: false,
    });
    expect(plan.request?.batchId).toBe("newer");
    expect(plan.jobCount).toBe(2);
  });

  it("treats a downloaded flag as ready", () => {
    expect(songIsReady(song())).toBe(true);
    expect(songIsReady(song({ downloaded_ok: false, output_dir_ok: "", output_dir_alt: "" }))).toBe(
      false,
    );
    expect(songIsReady(song({ downloaded_ok: false }))).toBe(true);
  });
});
