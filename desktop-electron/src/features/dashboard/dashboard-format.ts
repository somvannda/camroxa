import { formatCount, formatDateTime } from "../../lib/format";
import type {
  DashboardStats,
  DailyUsage,
  LicenseInfo,
  UserMe,
} from "./account-types";

export type KpiKey = "credits" | "songs" | "images" | "videos" | "youtube";

export interface KpiValue {
  key: KpiKey;
  label: string;
  value: string;
}

const KPI_LABELS: Record<KpiKey, string> = {
  credits: "Suno credit spent",
  songs: "Songs generated",
  images: "Images generated",
  videos: "Videos generated",
  youtube: "YouTube uploaded",
};

const KPI_ORDER: KpiKey[] = ["credits", "songs", "images", "videos", "youtube"];

export function percentOf(part: number, total: number): number {
  if (!Number.isFinite(part) || !Number.isFinite(total) || total <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((part / total) * 100)));
}

function placeholderKpis(): KpiValue[] {
  return KPI_ORDER.map((key) => ({ key, label: KPI_LABELS[key], value: "--" }));
}

export function kpiValues(stats: DashboardStats | null | undefined): KpiValue[] {
  if (!stats) return placeholderKpis();
  const values: Record<KpiKey, string> = {
    credits: formatCount(stats.credits_spent),
    songs: formatCount(stats.songs_generated),
    images: formatCount(stats.images_generated),
    videos: formatCount(stats.videos_generated),
    // Reference parity: the desktop summary reports uploaded videos from
    // `videos_generated`, which is the published figure the API provides.
    youtube: formatCount(stats.videos_generated),
  };
  return KPI_ORDER.map((key) => ({ key, label: KPI_LABELS[key], value: values[key] }));
}

export interface WeeklyDay {
  date: string;
  label: string;
  songs: number;
  images: number;
  videos: number;
  total: number;
}

const WEEK_LENGTH = 7;

function parseDayKey(value: string | null | undefined): string | null {
  if (!value) return null;
  const key = value.trim().slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(key) ? key : null;
}

export function formatShortDay(dayKey: string): string {
  const date = new Date(`${dayKey}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return dayKey;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function addDays(dayKey: string, amount: number): string {
  const date = new Date(`${dayKey}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + amount);
  return date.toISOString().slice(0, 10);
}

/**
 * Builds exactly seven day columns ending at the most recent day the API
 * reported. Missing days are filled with zeroes so the chart never silently
 * drops a gap in the window.
 */
export function buildWeeklySeries(usage: DailyUsage[] | null | undefined): WeeklyDay[] {
  const totals = new Map<string, { songs: number; images: number; videos: number }>();
  for (const entry of usage ?? []) {
    const key = parseDayKey(entry.date);
    if (!key) continue;
    const current = totals.get(key) ?? { songs: 0, images: 0, videos: 0 };
    current.songs += Math.max(0, Math.round(entry.songs ?? 0));
    current.images += Math.max(0, Math.round(entry.images ?? 0));
    current.videos += Math.max(0, Math.round(entry.videos ?? 0));
    totals.set(key, current);
  }

  const days = [...totals.keys()].sort();
  if (days.length === 0) return [];

  const end = days[days.length - 1];
  const window: WeeklyDay[] = [];
  for (let offset = WEEK_LENGTH - 1; offset >= 0; offset -= 1) {
    const date = addDays(end, -offset);
    const value = totals.get(date) ?? { songs: 0, images: 0, videos: 0 };
    window.push({
      date,
      label: formatShortDay(date),
      songs: value.songs,
      images: value.images,
      videos: value.videos,
      total: value.songs + value.images + value.videos,
    });
  }
  return window;
}

export interface PlanBadge {
  plan: string;
  expiry: string;
  expiryLine: string;
}

export function formatPlanName(raw: string | null | undefined): string {
  const trimmed = (raw ?? "").trim();
  if (!trimmed) return "No plan";
  const normalized = trimmed.replace(/[_\s]+/g, " ").toLowerCase();
  if (normalized === "none" || normalized === "free" || normalized === "no plan") {
    return "No plan";
  }
  const cycleMatch = trimmed.match(/[(\-_\s]+(monthly|yearly)\)?$/i);
  const cycle = cycleMatch?.[1]?.toLowerCase() ?? "";
  const base = trimmed
    .replace(/[(\-_\s]+(monthly|yearly)\)?$/i, "")
    .replace(/_/g, " ")
    .trim();
  const title = base
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
  const label = title || "Plan";
  if (cycle === "monthly") return `${label} (Monthly)`;
  if (cycle === "yearly") return `${label} (Yearly)`;
  return label;
}

export function shortExpiry(value: string | null | undefined): string | null {
  const key = parseDayKey(value);
  if (!key) return null;
  return formatShortDay(key);
}

export function planBadge(
  me: UserMe | null | undefined,
  license: LicenseInfo | null | undefined,
): PlanBadge {
  const plan = formatPlanName(license?.plan_type ?? me?.plan_name);
  const expiry = shortExpiry(license?.expiration_date);
  return {
    plan: plan === "No plan" ? "No plan" : plan,
    expiry: expiry ? `Expires ${expiry}` : "Expiration not provided",
    expiryLine: expiry ? `Expires: ${expiry}` : "Expires: Not provided",
  };
}

export interface QuotaRow {
  key: "credits" | "songs" | "images";
  label: string;
  value: string;
  percent: number;
  tone: "violet" | "sky" | "emerald";
}

export function quotaRows(
  stats: DashboardStats | null | undefined,
  license: LicenseInfo | null | undefined,
): QuotaRow[] {
  const loading = !stats;
  const creditsTotal = stats
    ? stats.credits_total || stats.credits_spent + stats.credits_remaining
    : 0;
  const creditsRemaining = stats?.credits_remaining ?? 0;

  const songQuota = license?.monthly_song_quota ?? stats?.songs_quota ?? null;
  const songsRemaining = license?.songs_remaining ?? stats?.songs_remaining ?? null;

  return [
    {
      key: "credits",
      label: "Credits",
      value: loading ? "--" : `${formatCount(creditsRemaining)} / ${formatCount(creditsTotal)}`,
      percent: loading ? 0 : percentOf(creditsRemaining, creditsTotal),
      tone: "violet",
    },
    {
      key: "songs",
      label: "Songs",
      value: loading
        ? "--"
        : songQuota !== null && songsRemaining !== null
          ? `${formatCount(songsRemaining)} / ${formatCount(songQuota)}`
          : "Not provided",
      percent:
        songQuota !== null && songsRemaining !== null
          ? percentOf(songsRemaining, songQuota)
          : 0,
      tone: "sky",
    },
    {
      key: "images",
      label: "Images",
      value: loading ? "--" : "0 / 1",
      percent: 0,
      tone: "emerald",
    },
  ];
}

export interface SummaryLine {
  label: string;
  value: string;
}

export function quotaSummary(
  me: UserMe | null | undefined,
  stats: DashboardStats | null | undefined,
  license: LicenseInfo | null | undefined,
): SummaryLine[] {
  if (!stats || !me) {
    return [
      { label: "Credits balance", value: "--" },
      { label: "Song quota", value: "--" },
      { label: "Image quota", value: "--" },
    ];
  }

  const wallet = license?.wallet_balance ?? me.credit_balance;
  const songQuota = license?.monthly_song_quota ?? stats.songs_quota ?? null;
  const imageQuota = license?.monthly_image_quota ?? stats.images_quota ?? 0;

  return [
    { label: "Credits balance", value: formatCount(wallet) },
    {
      label: "Song quota",
      value: songQuota !== null ? formatCount(songQuota) : "Not provided",
    },
    { label: "Image quota", value: formatCount(imageQuota) },
  ];
}

export interface ActivityRow {
  key: string;
  time: string;
  type: string;
  batch: string;
  channel: string;
  stage: string;
  detail: string;
}

export function activityRows(
  stats: DashboardStats | null | undefined,
  limit = 20,
): ActivityRow[] {
  const entries = [...(stats?.recent_activity ?? [])];
  entries.sort((a, b) => {
    const left = new Date(a.timestamp).getTime();
    const right = new Date(b.timestamp).getTime();
    if (Number.isNaN(left) && Number.isNaN(right)) return 0;
    if (Number.isNaN(left)) return 1;
    if (Number.isNaN(right)) return -1;
    return right - left;
  });

  return entries.slice(0, limit).map((entry, index) => ({
    key: `${entry.timestamp}-${entry.kind}-${index}`,
    time: entry.timestamp ? formatDateTime(entry.timestamp) : "--",
    type: entry.kind || "--",
    batch: "--",
    channel: "--",
    stage: entry.status || "--",
    detail: entry.detail || "--",
  }));
}

export type ActivityTone = "neutral" | "success" | "warning" | "danger" | "accent";

export function activityTone(status: string | null | undefined): ActivityTone {
  const key = (status ?? "").trim().toLowerCase();
  if (["success", "completed", "complete", "done", "ready", "uploaded"].includes(key)) {
    return "success";
  }
  if (["failed", "failure", "error", "cancelled", "canceled"].includes(key)) {
    return "danger";
  }
  if (["running", "pending", "queued", "processing", "waiting"].includes(key)) {
    return "warning";
  }
  if (["scheduled", "deferred"].includes(key)) return "accent";
  return "neutral";
}
