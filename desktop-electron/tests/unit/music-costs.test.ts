import { describe, expect, it } from "vitest";
import {
  formatButtonCredits,
  formatCreditLine,
  formatCredits,
  formatPlanLine,
  planCostBreakdown,
  profileImageJobCount,
  type PlanCostInput,
} from "../../src/features/music/music-costs";
import type { ChannelProfile, OperationCost } from "../../src/features/music/music-types";

const profile = (id: string, name: string, mode = "bg_thumb"): ChannelProfile => ({
  id,
  name,
  image_config: { mode },
});

const costs: Record<string, OperationCost> = {
  lyric: { operation_type: "lyric", credits_per_operation: 3, available: true },
  title: { operation_type: "title", credits_per_operation: 0, available: true },
  album: { operation_type: "album", credits_per_operation: 0, available: true },
  music: { operation_type: "music", credits_per_operation: 7, available: true },
  image: { operation_type: "background_image", credits_per_operation: 5, available: true },
  video: { operation_type: "video", credits_per_operation: 3, available: true },
  merge: { operation_type: "video_merge", credits_per_operation: 10, available: true },
};

function input(overrides: Partial<PlanCostInput> = {}): PlanCostInput {
  return {
    lyricCost: costs.lyric,
    titleCost: costs.title,
    albumCost: costs.album,
    musicCost: costs.music,
    imageCost: costs.image,
    videoCost: costs.video,
    mergeCost: costs.merge,
    primary: [profile("ok", "Primary")],
    secondary: [profile("alt", "Secondary")],
    songCount: 4,
    autoGenImage: false,
    autoGSuno: false,
    autoVideo: false,
    autoMerge: false,
    autoReel: false,
    autoUpload: false,
    dayCount: 1,
    imageSourceMode: "ai",
    ...overrides,
  };
}

describe("music credit parity", () => {
  it("default 1 day / 1 pair / 4 songs = 12 credits", () => {
    const breakdown = planCostBreakdown(input());
    expect(breakdown?.total).toBe(12);
    expect(breakdown?.draftTotal).toBe(12);
    expect(breakdown?.sunoTotal).toBe(0);
    expect(breakdown?.imageTotal).toBe(0);
  });

  it("Auto-Image = 92 credits with image total 80", () => {
    const breakdown = planCostBreakdown(input({ autoGenImage: true }));
    expect(breakdown?.imageTotalJobs).toBe(16);
    expect(breakdown?.imageTotal).toBe(80);
    expect(breakdown?.total).toBe(92);
  });

  it("Auto-GSuno = 40 credits with suno total 28", () => {
    const breakdown = planCostBreakdown(input({ autoGSuno: true }));
    expect(breakdown?.sunoTotal).toBe(28);
    expect(breakdown?.total).toBe(40);
  });

  it("3 days + Auto-GSuno = 120 credits", () => {
    const breakdown = planCostBreakdown(input({ autoGSuno: true, dayCount: 3 }));
    expect(breakdown?.batchCount).toBe(3);
    expect(breakdown?.songJobs).toBe(12);
    expect(breakdown?.draftTotal).toBe(36);
    expect(breakdown?.sunoTotal).toBe(84);
    expect(breakdown?.total).toBe(120);
  });

  it("excludes image costs when imageSourceMode is manual", () => {
    const breakdown = planCostBreakdown(
      input({ autoGenImage: true, imageSourceMode: "manual" }),
    );
    expect(breakdown?.imageTotalJobs).toBe(0);
    expect(breakdown?.imageTotal).toBe(0);
    expect(breakdown?.total).toBe(12);
  });

  it("counts one image job for bg_only and thumb_only channels", () => {
    expect(profileImageJobCount(profile("a", "A", "bg_only"))).toBe(1);
    expect(profileImageJobCount(profile("b", "B", "thumb_only"))).toBe(1);
    expect(profileImageJobCount(profile("c", "C", "bg_thumb"))).toBe(2);
    expect(profileImageJobCount(null)).toBe(2);
  });

  it("prices video and merge only after Suno, doubling with Auto-Reel", () => {
    const video = planCostBreakdown(
      input({ autoGSuno: true, autoVideo: true, autoMerge: true }),
    );
    expect(video?.videoOps).toBe(8);
    expect(video?.videoTotal).toBe(24);
    expect(video?.mergeOps).toBe(2);
    expect(video?.mergeTotal).toBe(20);
    expect(video?.videoMergeTotal).toBe(44);
    expect(video?.total).toBe(84);

    const reel = planCostBreakdown(
      input({ autoGSuno: true, autoVideo: true, autoMerge: true, autoReel: true }),
    );
    expect(reel?.videoOps).toBe(16);
    expect(reel?.mergeOps).toBe(4);

    const noSuno = planCostBreakdown(input({ autoVideo: true, autoMerge: true }));
    expect(noSuno?.videoOps).toBe(0);
    expect(noSuno?.mergeOps).toBe(0);
    expect(noSuno?.total).toBe(12);
  });

  it("adds title and album when the backend prices them", () => {
    const breakdown = planCostBreakdown(
      input({
        titleCost: { operation_type: "title", credits_per_operation: 1, available: true },
        albumCost: { operation_type: "album", credits_per_operation: 2, available: true },
      }),
    );
    expect(breakdown?.draftTotal).toBe(3 * 4 + 1 * 4 + 2 * 1);
  });

  it("returns null totals when the lyric price is unavailable", () => {
    const breakdown = planCostBreakdown(
      input({ lyricCost: { operation_type: "lyric", credits_per_operation: null } }),
    );
    expect(breakdown?.draftTotal).toBeNull();
    expect(breakdown?.total).toBeNull();
  });

  it("returns no plan for missing or mismatched pairs and ranges", () => {
    expect(planCostBreakdown(input({ primary: [], secondary: [] }))).toBeNull();
    expect(
      planCostBreakdown(input({ secondary: [profile("a", "A"), profile("b", "B")] })),
    ).toBeNull();
    expect(planCostBreakdown(input({ dayCount: null }))).toBeNull();
  });
});

describe("music credit formatting", () => {
  it("formats labels exactly as the page document expects", () => {
    expect(formatCredits(3)).toBe("3");
    expect(formatCredits(99.40090000000001)).toBe("99.4");
    expect(formatCredits(null)).toBe("unavailable");
    expect(formatCreditLine("Draft", 3)).toBe("Draft: 3 credits");
    expect(formatCreditLine("Polish", 3)).toBe("Polish: 3 credits");
    expect(formatCreditLine("Suno", 7)).toBe("Suno: 7 credits");
    expect(formatCreditLine("Image", 5)).toBe("Image: 5 credits");
    expect(formatCreditLine("Draft", null)).toBe("Draft: unavailable");
    expect(formatButtonCredits("Generate", 12)).toBe("Generate (12 credits)");
    expect(formatButtonCredits("Generate", null)).toBe("Generate");
  });

  it("builds the documented plan line", () => {
    const breakdown = planCostBreakdown(input());
    expect(formatPlanLine(breakdown)).toBe("1 day x 1 pair x 4 songs = 4 song jobs");
    const threeDays = planCostBreakdown(input({ autoGSuno: true, dayCount: 3 }));
    expect(formatPlanLine(threeDays)).toBe("3 days x 1 pair x 4 songs = 12 song jobs");
    expect(formatPlanLine(null)).toBe(
      "Select dates and matching channel pairs to estimate this run.",
    );
  });
});
