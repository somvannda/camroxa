import { describe, expect, it } from "vitest";
import type {
  DashboardStats,
  DailyUsage,
  UserMe,
} from "../../src/features/dashboard/account-types";
import {
  activityRows,
  activityTone,
  buildWeeklySeries,
  creditPosition,
  formatPlanName,
  kpiValues,
  percentOf,
} from "../../src/features/dashboard/dashboard-format";
import {
  chartX,
  chartY,
  gridLineYs,
  monotonePath,
  seriesPoints,
  CHART_PADDING,
} from "../../src/features/dashboard/chart";

const stats = {
  credits_spent: 1234,
  credits_remaining: 750,
  credits_total: 2000,
  songs_generated: 12,
  songs_remaining: 76,
  songs_quota: 120,
  images_remaining: null,
  images_quota: null,
  drafts_remaining: null,
  drafts_quota: null,
  images_generated: 5,
  studio_exports: 3,
  manual_exports: 2,
  youtube_uploads: 1,
  videos_generated: 3,
  videos_uploaded: 1,
  usage_by_day: [],
  recent_activity: [],
} satisfies DashboardStats;

const me = {
  id: "user-1",
  email: "operator@example.com",
  email_confirmed: true,
  display_name: "Operator",
  avatar_url: null,
  role: "user",
  status: "active",
  suspension_reason: null,
  credit_balance: 500,
  plan_name: "studio-monthly",
  music_credits_remaining: null,
  music_credits_limit: null,
  credits_burned: null,
  profile_allowance: 5,
  profile_addon_slots: 0,
  profile_addon_pending: 0,
  effective_profile_allowance: 6,
  effective_quota_channels: null,
  channel_profile_count: 3,
  onboarding_paid: true,
  desktop_access: true,
  products: [],
  pending_verification_code: null,
  verification_code_expires_at: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: null,
} satisfies UserMe;

describe("dashboard format", () => {
  it("maps the six credit-first KPI cards and keeps placeholders while loading", () => {
    const values = kpiValues(stats, me);
    expect(values.map((item) => item.label)).toEqual([
      "Credit balance",
      "Credits spent",
      "Songs generated",
      "Images generated",
      "Videos rendered",
      "YouTube uploads",
    ]);
    expect(values.map((item) => item.value)).toEqual(["750", "1,234", "12", "5", "3", "1"]);
    expect(kpiValues(null).every((item) => item.value === "--")).toBe(true);
    expect(kpiValues(null)).toHaveLength(6);
  });

  it("builds a seven day window ending at the newest usage day", () => {
    const usage: DailyUsage[] = [
      { date: "2026-11-10", songs: 1, images: 0, videos: 0, studio_exports: 0, manual_exports: 0, youtube_uploads: 0 },
      { date: "2026-11-16", songs: 2, images: 1, videos: 0, studio_exports: 0, manual_exports: 0, youtube_uploads: 0 },
      { date: "2026-11-16", songs: 3, images: 0, videos: 1, studio_exports: 0, manual_exports: 0, youtube_uploads: 0 },
    ];
    const series = buildWeeklySeries(usage);
    expect(series).toHaveLength(7);
    expect(series[0].date).toBe("2026-11-10");
    expect(series[6].date).toBe("2026-11-16");
    expect(series[6]).toMatchObject({ songs: 5, images: 1, videos: 1, total: 7 });
    expect(series[1].label).toBe("Nov 11");
    expect(buildWeeklySeries([])).toEqual([]);
    expect(buildWeeklySeries(null)).toEqual([]);
  });

  it("normalises plan labels for the profile page", () => {
    expect(formatPlanName("studio-monthly")).toBe("Studio (Monthly)");
    expect(formatPlanName("no plan")).toBe("No plan");
    expect(formatPlanName("")).toBe("No plan");
  });

  it("describes a credits-only balance with spend, exports and uploads", () => {
    const position = creditPosition(stats, me);
    expect(position).toMatchObject({
      balance: 750,
      spent: 1234,
      total: 2000,
      percentUsed: 62,
      studioExports: 3,
      manualExports: 2,
      youtubeUploads: 1,
    });
    // Falls back to the wallet when the stats balance is zero.
    const fallback = creditPosition({ ...stats, credits_remaining: 0 }, { ...me, credit_balance: 420 });
    expect(fallback?.balance).toBe(420);
    expect(creditPosition(null, me)).toBeNull();
  });

  it("lists newest activity first with grouped days", () => {
    const rows = activityRows({
      ...stats,
      recent_activity: [
        { timestamp: "2026-11-18T10:00:00Z", kind: "song", detail: "Batch A", status: "completed" },
        { timestamp: "2026-11-19T09:30:00Z", kind: "image", detail: "Cover", status: "failed" },
      ],
    });
    expect(rows[0].kind).toBe("Image");
    expect(rows[0].status).toBe("failed");
    expect(rows[1].kind).toBe("Song");
    expect(rows[0].time).toBeTruthy();
    expect(rows[0].group).toBeTruthy();
    expect(activityRows(stats)).toEqual([]);
    const many = Array.from({ length: 30 }, (_, index) => ({
      timestamp: `2026-11-${String((index % 9) + 10).padStart(2, "0")}T10:00:00Z`,
      kind: "song",
      detail: "x",
      status: "completed",
    }));
    expect(activityRows({ ...stats, recent_activity: many })).toHaveLength(24);
  });

  it("maps statuses to badge tones and clamps percents", () => {
    expect(activityTone("Completed")).toBe("success");
    expect(activityTone("failed")).toBe("danger");
    expect(activityTone("queued")).toBe("warning");
    expect(activityTone("scheduled")).toBe("accent");
    expect(activityTone("unknown")).toBe("neutral");
    expect(percentOf(5, 0)).toBe(0);
    expect(percentOf(150, 100)).toBe(100);
    expect(percentOf(-5, 100)).toBe(0);
  });
});

describe("chart geometry", () => {
  it("places points with the documented vertical formula", () => {
    expect(chartY(0, 10, 220)).toBe(200);
    expect(chartY(10, 10, 220)).toBe(20);
    expect(chartY(5, 10, 220)).toBe(110);
    expect(chartY(4, 0, 220)).toBe(200);
    expect(chartX(0, 7, 640)).toBe(CHART_PADDING);
    expect(chartX(6, 7, 640)).toBe(620);
    expect(chartX(0, 1, 640)).toBe(320);
  });

  it("scales each series by its own maximum", () => {
    const songs = seriesPoints([0, 5, 10], 640, 220);
    const images = seriesPoints([0, 50, 100], 640, 220);
    expect(songs.split(" ")[2]).toBe("620,20");
    expect(images.split(" ")[2]).toBe("620,20");
  });

  it("draws four dashed grid lines", () => {
    const lines = gridLineYs(220);
    expect(lines).toHaveLength(4);
    expect(lines[0]).toBe(20);
    expect(lines[3]).toBe(200);
  });

  it("builds a monotone cubic path that starts at the first point", () => {
    const path = monotonePath(
      [
        { x: 0, y: 100 },
        { x: 50, y: 100 },
        { x: 100, y: 20 },
      ],
      10,
      110,
    );
    expect(path.startsWith("M 0 100")).toBe(true);
    expect(path).toContain(" C ");
    expect(path).toContain("100 20");
    expect(path).not.toContain("NaN");
    // A flat run into a spike must not dip above the first point.
    expect(monotonePath([{ x: 0, y: 100 }])).toBe("M 0 100");
    expect(monotonePath([])).toBe("");
  });
});
