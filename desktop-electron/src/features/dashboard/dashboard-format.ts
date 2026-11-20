import { formatCount, formatDateTime } from "../../lib/format";
import type {
  DashboardStats,
  DailyUsage,
  UserMe,
} from "./account-types";

export type KpiKey = "balance" | "spent" | "songs" | "images" | "videos" | "uploads";

export interface KpiValue {
  key: KpiKey;
  label: string;
  value: string;
  hint: string;
}

const KPI_LABELS: Record<KpiKey, string> = {
  balance: "Credit balance",
  spent: "Credits spent",
  songs: "Songs generated",
  images: "Images generated",
  videos: "Videos rendered",
  uploads: "YouTube uploads",
};

const KPI_ORDER: KpiKey[] = ["balance", "spent", "songs", "images", "videos", "uploads"];

export function percentOf(part: number, total: number): number {
  if (!Number.isFinite(part) || !Number.isFinite(total) || total <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((part / total) * 100)));
}

function placeholderKpis(): KpiValue[] {
  return KPI_ORDER.map((key) => ({ key, label: KPI_LABELS[key], value: "--", hint: "" }));
}

export function kpiValues(
  stats: DashboardStats | null | undefined,
  me?: UserMe | null,
): KpiValue[] {
  if (!stats) return placeholderKpis();
  const total = stats.credits_total || stats.credits_spent + stats.credits_remaining;
  const balance = stats.credits_remaining || me?.credit_balance || 0;
  const hints: Record<KpiKey, string> = {
    balance: total > 0 ? `${formatCount(total)} credits granted` : "Available now",
    spent: "Across all runs",
    songs: "Suno tracks",
    images: "Covers and thumbnails",
    videos: "Vizzy renders",
    uploads: "Published manually",
  };
  const values: Record<KpiKey, string> = {
    balance: formatCount(balance),
    spent: formatCount(stats.credits_spent),
    songs: formatCount(stats.songs_generated),
    images: formatCount(stats.images_generated),
    videos: formatCount(stats.videos_generated),
    uploads: formatCount(stats.youtube_uploads),
  };
  return KPI_ORDER.map((key) => ({
    key,
    label: KPI_LABELS[key],
    value: values[key],
    hint: hints[key],
  }));
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

export interface CreditPosition {
  balance: number;
  spent: number;
  total: number;
  percentUsed: number;
  studioExports: number;
  manualExports: number;
  youtubeUploads: number;
  lastExport: string;
}

/**
 * The account is credits-only: there is no plan allowance or song/image quota.
 * Everything is expressed against the wallet so the card never implies a
 * leftover quota that the backend no longer grants.
 */
export function creditPosition(
  stats: DashboardStats | null | undefined,
  me: UserMe | null | undefined,
): CreditPosition | null {
  if (!stats) return null;
  const balance = stats.credits_remaining || me?.credit_balance || 0;
  const spent = Math.max(0, stats.credits_spent);
  const total = stats.credits_total || spent + balance;
  return {
    balance,
    spent,
    total,
    percentUsed: percentOf(spent, total),
    studioExports: stats.studio_exports,
    manualExports: stats.manual_exports,
    youtubeUploads: stats.youtube_uploads,
    lastExport: stats.last_export_at ? formatDateTime(stats.last_export_at) : "Not yet",
  };
}

export interface ActivityRow {
  key: string;
  timestamp: string;
  group: string;
  time: string;
  kind: string;
  detail: string;
  status: string;
}

const DAY_MS = 24 * 60 * 60 * 1000;

function startOfDay(date: Date): number {
  return Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
}

function activityGroup(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Earlier";
  const now = new Date();
  const today = startOfDay(now);
  const day = startOfDay(date);
  if (day === today) return "Today";
  if (day === today - DAY_MS) return "Yesterday";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function activityTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function humanizeKind(kind: string): string {
  const text = (kind ?? "").trim().replace(/[_-]+/g, " ");
  if (!text) return "Activity";
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function activityRows(
  stats: DashboardStats | null | undefined,
  limit = 24,
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
    timestamp: entry.timestamp,
    group: activityGroup(entry.timestamp),
    time: activityTime(entry.timestamp),
    kind: humanizeKind(entry.kind),
    detail: entry.detail || "No detail provided.",
    status: entry.status || "unknown",
  }));
}

export function activityIcon(kind: string): string {
  const key = (kind ?? "").toLowerCase();
  if (key.includes("song") || key.includes("music") || key.includes("draft")) return "fa-music";
  if (key.includes("image")) return "fa-image";
  if (key.includes("video") || key.includes("render")) return "fa-video";
  if (key.includes("upload") || key.includes("youtube")) return "fa-cloud-arrow-up";
  if (key.includes("credit") || key.includes("purchase")) return "fa-coins";
  if (key.includes("export")) return "fa-file-export";
  return "fa-bolt";
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
