import { formatCount, formatCredits } from "../../lib/format";
import type {
  ChannelProfile,
  DashboardStats,
  LicenseInfo,
  UserMe,
} from "../dashboard/account-types";
import { percentOf } from "../dashboard/dashboard-format";

const IMAGE_MODE_LABELS: Record<string, string> = {
  bg_thumb: "BG + TH",
  bg_only: "BG Only",
  thumb_only: "TH Only",
};

const VISIBILITY_LABELS: Record<string, string> = {
  public: "Public",
  unlisted: "Unlisted",
  private: "Private",
  scheduled: "Scheduled",
};

export function imageModeLabel(profile: ChannelProfile | null | undefined): string {
  const config = (profile?.image_config ?? {}) as Record<string, unknown>;
  const mode = String(config.mode ?? "bg_thumb").trim().toLowerCase();
  return IMAGE_MODE_LABELS[mode] ?? "BG + TH";
}

export function visibilityLabel(profile: ChannelProfile | null | undefined): string {
  const config = (profile?.youtube_config ?? {}) as Record<string, unknown>;
  const raw = String(config.visibility ?? "unlisted").trim().toLowerCase();
  if (VISIBILITY_LABELS[raw]) return VISIBILITY_LABELS[raw];
  if (!raw) return "Unlisted";
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

export function planSubtitle(planName: string | null | undefined): string {
  const text = String(planName ?? "").trim().toLowerCase();
  if (text.includes("year") || text.includes("annual")) return "Annual plan";
  if (text.includes("week")) return "Weekly plan";
  if (text) return "Credit pack";
  return "No active plan";
}

export function profileAllowance(
  me: UserMe | null | undefined,
  profileCount: number,
): { used: number; allowance: number | null; text: string; percent: number } {
  const allowance = me?.effective_profile_allowance ?? me?.profile_allowance ?? null;
  const used = me?.channel_profile_count ?? profileCount;
  if (allowance === null) {
    return { used, allowance: null, text: `${formatCount(used)}`, percent: 0 };
  }
  return {
    used,
    allowance,
    text: `${formatCount(used)} / ${formatCount(allowance)}`,
    percent: percentOf(used, allowance),
  };
}

export interface ProfileMetric {
  key: "profiles" | "credits";
  label: string;
  value: string;
  percent: number;
  tone: "emerald" | "sky";
}

export function membershipMetrics(
  me: UserMe | null | undefined,
  stats: DashboardStats | null | undefined,
  _license: LicenseInfo | null | undefined,
  profileCount: number,
): ProfileMetric[] {
  const profiles = profileAllowance(me, profileCount);
  const total = stats ? stats.credits_total || stats.credits_spent + stats.credits_remaining : 0;
  const spent = stats?.credits_spent ?? 0;

  return [
    {
      key: "profiles",
      label: "Profiles",
      value: profiles.text,
      percent: profiles.percent,
      tone: "emerald",
    },
    {
      key: "credits",
      label: "Credits used",
      value: stats ? `${formatCredits(spent)} / ${formatCredits(total)}` : "Not provided",
      percent: percentOf(spent, total),
      tone: "sky",
    },
  ];
}

export interface MembershipField {
  label: string;
  value: string;
}

export function membershipFields(
  me: UserMe | null | undefined,
  stats: DashboardStats | null | undefined,
): MembershipField[] {
  const wallet = me?.credit_balance ?? null;
  return [
    { label: "Credits balance", value: wallet !== null ? formatCredits(wallet) : "--" },
    { label: "Credits spent", value: stats ? formatCredits(stats.credits_spent) : "--" },
    { label: "Songs", value: stats ? formatCount(stats.songs_generated) : "--" },
    { label: "Images", value: stats ? formatCount(stats.images_generated) : "--" },
    { label: "Videos", value: stats ? formatCount(stats.videos_generated) : "--" },
    { label: "YouTube uploads", value: stats ? formatCount(stats.youtube_uploads) : "--" },
  ];
}

export function accountName(me: UserMe | null | undefined): string {
  if (!me) return "Loading account...";
  const name = me.display_name?.trim();
  return name || me.email?.trim() || "Camxora user";
}

export function accountInitials(me: UserMe | null | undefined): string {
  if (!me) return "?";
  const source = me.display_name?.trim() || me.email?.trim() || "";
  const initials = source
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return initials || "?";
}

export function sortProfiles(profiles: ChannelProfile[] | null | undefined): ChannelProfile[] {
  return [...(profiles ?? [])].sort((a, b) =>
    (a.name ?? "").localeCompare(b.name ?? "", undefined, { sensitivity: "base" }),
  );
}

export function profileCounters(
  stats: DashboardStats | null | undefined,
): Array<{ label: string; value: string }> {
  if (!stats) {
    return [
      { label: "Songs generated", value: "--" },
      { label: "Images generated", value: "--" },
      { label: "Videos generated", value: "--" },
      { label: "Credits spent", value: "--" },
    ];
  }
  return [
    { label: "Songs generated", value: formatCount(stats.songs_generated) },
    { label: "Images generated", value: formatCount(stats.images_generated) },
    { label: "Videos generated", value: formatCount(stats.videos_generated) },
    { label: "Credits spent", value: formatCredits(stats.credits_spent) },
  ];
}
