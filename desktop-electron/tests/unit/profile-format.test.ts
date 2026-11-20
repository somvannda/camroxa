import { describe, expect, it } from "vitest";
import type {
  ChannelProfile,
  DashboardStats,
  LicenseInfo,
  UserMe,
} from "../../src/features/dashboard/account-types";
import {
  accountInitials,
  accountName,
  imageModeLabel,
  membershipFields,
  membershipMetrics,
  planSubtitle,
  profileAllowance,
  profileCounters,
  sortProfiles,
  visibilityLabel,
} from "../../src/features/profile/profile-format";

const profile = {
  id: "p1",
  user_id: "u1",
  name: "Night Shift",
  folder_name: "night-shift",
  run_prefix: "NS",
  logo_path: null,
  video_template_id: null,
  reel_template_id: null,
  output_resolution: "1920x1080",
  image_config: { mode: "bg_only" },
  youtube_config: { visibility: "public" },
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
} satisfies ChannelProfile;

const me = {
  id: "u1",
  email: "operator@example.com",
  email_confirmed: false,
  display_name: "Night Operator",
  avatar_url: null,
  role: "user",
  status: "active",
  suspension_reason: null,
  credit_balance: 320,
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

const stats = {
  credits_spent: 980,
  credits_remaining: 20,
  credits_total: 1000,
  songs_generated: 40,
  songs_remaining: 76,
  songs_quota: 120,
  images_remaining: null,
  images_quota: null,
  drafts_remaining: null,
  drafts_quota: null,
  images_generated: 12,
  studio_exports: 3,
  manual_exports: 1,
  youtube_uploads: 2,
  videos_generated: 3,
  videos_uploaded: 2,
  usage_by_day: [],
  recent_activity: [],
} satisfies DashboardStats;

describe("profile helpers", () => {
  it("maps image mode and visibility labels", () => {
    expect(imageModeLabel({ ...profile, image_config: { mode: "bg_thumb" } })).toBe("BG + TH");
    expect(imageModeLabel({ ...profile, image_config: { mode: "bg_only" } })).toBe("BG Only");
    expect(imageModeLabel({ ...profile, image_config: { mode: "thumb_only" } })).toBe("TH Only");
    expect(imageModeLabel({ ...profile, image_config: {} })).toBe("BG + TH");
    expect(imageModeLabel(null)).toBe("BG + TH");

    expect(visibilityLabel({ ...profile, youtube_config: { visibility: "public" } })).toBe("Public");
    expect(visibilityLabel({ ...profile, youtube_config: { visibility: "unlisted" } })).toBe("Unlisted");
    expect(visibilityLabel({ ...profile, youtube_config: { visibility: "private" } })).toBe("Private");
    expect(visibilityLabel({ ...profile, youtube_config: { visibility: "scheduled" } })).toBe("Scheduled");
    expect(visibilityLabel({ ...profile, youtube_config: {} })).toBe("Unlisted");
  });

  it("computes profile allowance from the effective value", () => {
    expect(profileAllowance(me, 3)).toEqual({
      used: 3,
      allowance: 6,
      text: "3 / 6",
      percent: 50,
    });
    expect(profileAllowance({ ...me, effective_profile_allowance: null }, 3)).toMatchObject({
      allowance: 5,
      text: "3 / 5",
      percent: 60,
    });
    expect(profileAllowance({ ...me, effective_profile_allowance: null, profile_allowance: null }, 2)).toMatchObject({
      allowance: null,
      text: "3",
      percent: 0,
    });
  });

  it("builds credits-first membership metrics in the profile style", () => {
    const licence: LicenseInfo = { monthly_song_quota: 120, songs_remaining: 76, wallet_balance: 400 };
    const metrics = membershipMetrics(me, stats, licence, 1);
    expect(metrics[0]).toMatchObject({ key: "profiles", label: "Profiles", value: "3 / 6", percent: 50 });
    expect(metrics[1]).toMatchObject({
      key: "credits",
      label: "Credits used",
      value: "980 / 1,000",
      percent: 98,
      tone: "sky",
    });
    expect(membershipMetrics(me, null, null, 1)[1].value).toBe("Not provided");
  });

  it("fills membership fields from credits and lifetime counters", () => {
    expect(membershipFields(me, stats)).toEqual([
      { label: "Credits balance", value: "320" },
      { label: "Credits spent", value: "980" },
      { label: "Songs", value: "40" },
      { label: "Images", value: "12" },
      { label: "Videos", value: "3" },
      { label: "YouTube uploads", value: "2" },
    ]);
    expect(membershipFields(me, null).map((field) => field.value)).toEqual([
      "320",
      "--",
      "--",
      "--",
      "--",
      "--",
    ]);
    expect(planSubtitle("studio-yearly")).toBe("Annual plan");
    expect(planSubtitle("weekly")).toBe("Weekly plan");
    expect(planSubtitle("credit-pack")).toBe("Credit pack");
    expect(planSubtitle("")).toBe("No active plan");
  });

  it("formats identity and counters", () => {
    expect(accountName(me)).toBe("Night Operator");
    expect(accountName({ ...me, display_name: "" })).toBe("operator@example.com");
    expect(accountName(null)).toBe("Loading account...");
    expect(accountInitials(me)).toBe("NO");
    expect(accountInitials(null)).toBe("?");
    expect(profileCounters(stats)).toEqual([
      { label: "Songs generated", value: "40" },
      { label: "Images generated", value: "12" },
      { label: "Videos generated", value: "3" },
      { label: "Credits spent", value: "980" },
    ]);
    expect(profileCounters(null).every((item) => item.value === "--")).toBe(true);
  });

  it("sorts channel profiles by name", () => {
    const sorted = sortProfiles([
      { ...profile, id: "b", name: "beta" },
      { ...profile, id: "a", name: "Alpha" },
    ]);
    expect(sorted.map((item) => item.name)).toEqual(["Alpha", "beta"]);
    expect(sortProfiles(null)).toEqual([]);
  });
});
