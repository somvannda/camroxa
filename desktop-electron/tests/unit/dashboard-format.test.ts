import { describe, expect, it } from "vitest";
import type {
  DashboardStats,
  DailyUsage,
  LicenseInfo,
  UserMe,
} from "../../src/features/dashboard/account-types";
import {
  activityRows,
  activityTone,
  buildWeeklySeries,
  formatPlanName,
  kpiValues,
  percentOf,
  planBadge,
  quotaRows,
  quotaSummary,
} from "../../src/features/dashboard/dashboard-format";
import {
  chartX,
  chartY,
  gridLineYs,
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
  it("maps the five KPI cards and keeps placeholders while loading", () => {
    const values = kpiValues(stats);
    expect(values.map((item) => item.label)).toEqual([
      "Suno credit spent",
      "Songs generated",
      "Images generated",
      "Videos generated",
      "YouTube uploaded",
    ]);
    expect(values.map((item) => item.value)).toEqual(["1,234", "12", "5", "3", "3"]);
    expect(kpiValues(null).every((item) => item.value === "--")).toBe(true);
    expect(kpiValues(null)).toHaveLength(5);
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

  it("normalises plan labels and expiry copy", () => {
    expect(formatPlanName("studio-monthly")).toBe("Studio (Monthly)");
    expect(formatPlanName("no plan")).toBe("No plan");
    expect(formatPlanName("")).toBe("No plan");
    const license: LicenseInfo = { plan_type: "pro_yearly", expiration_date: "2026-12-31" };
    expect(planBadge(me, license)).toEqual({
      plan: "Pro (Yearly)",
      expiry: "Expires Dec 31",
      expiryLine: "Expires: Dec 31",
    });
    expect(planBadge(me, null).expiry).toBe("Expiration not provided");
    expect(planBadge(me, null).expiryLine).toBe("Expires: Not provided");
  });

  it("derives remaining-month rows from licence then stats", () => {
    const licence: LicenseInfo = {
      monthly_song_quota: 120,
      songs_remaining: 76,
      wallet_balance: 400,
    };
    const rows = quotaRows(stats, licence);
    expect(rows[0]).toMatchObject({ key: "credits", value: "750 / 2,000", percent: 38 });
    expect(rows[1]).toMatchObject({ key: "songs", value: "76 / 120", percent: 63 });
    expect(rows[2]).toMatchObject({ key: "images", value: "0 / 1", percent: 0 });

    const noQuota = quotaRows(stats, null);
    expect(noQuota[1].value).toBe("76 / 120");
    expect(quotaRows(null, null)[0].value).toBe("--");
    expect(quotaRows(null, null)[1].value).toBe("--");
  });

  it("summarises the quota box with honest fallbacks", () => {
    expect(quotaSummary(me, stats, null)).toEqual([
      { label: "Credits balance", value: "500" },
      { label: "Song quota", value: "120" },
      { label: "Image quota", value: "0" },
    ]);
    expect(quotaSummary({ ...me, credit_balance: 0 }, { ...stats, songs_quota: null }, null)[1]).toEqual({
      label: "Song quota",
      value: "Not provided",
    });
    expect(quotaSummary(null, null, null).every((line) => line.value === "--")).toBe(true);
  });

  it("lists newest activity first with placeholder batch and channel", () => {
    const rows = activityRows({
      ...stats,
      recent_activity: [
        { timestamp: "2026-11-18T10:00:00Z", kind: "song", detail: "Batch A", status: "completed" },
        { timestamp: "2026-11-19T09:30:00Z", kind: "image", detail: "Cover", status: "failed" },
      ],
    });
    expect(rows[0].type).toBe("image");
    expect(rows[0].batch).toBe("--");
    expect(rows[0].channel).toBe("--");
    expect(rows[1].type).toBe("song");
    expect(rows[0].time).toContain("2026");
    expect(activityRows(stats)).toEqual([]);
    const many = Array.from({ length: 25 }, (_, index) => ({
      timestamp: `2026-11-${String((index % 9) + 10).padStart(2, "0")}T10:00:00Z`,
      kind: "song",
      detail: "x",
      status: "completed",
    }));
    expect(activityRows({ ...stats, recent_activity: many })).toHaveLength(20);
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
});
