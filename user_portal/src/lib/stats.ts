"use client";

import { platformJson } from "@/lib/auth-fetch";

export type DailyUsage = {
  date: string;
  songs: number;
  images: number;
  videos: number;
  studio_exports?: number;
  manual_exports?: number;
  youtube_uploads?: number;
};

export type RecentActivity = {
  timestamp: string;
  kind: string;
  detail: string;
  status: string;
};

export type DashboardStats = {
  credits_spent: number;
  credits_remaining: number;
  credits_total: number;
  songs_generated: number;
  songs_remaining: number | null;
  songs_quota: number | null;
  images_generated: number;
  images_remaining: number | null;
  images_quota: number | null;
  drafts_remaining?: number | null;
  drafts_quota?: number | null;
  studio_exports?: number;
  manual_exports?: number;
  youtube_uploads?: number;
  videos_generated: number;
  videos_uploaded: number;
  avg_studio_export_ms?: number | null;
  avg_manual_export_ms?: number | null;
  last_export_at?: string | null;
  usage_by_day: DailyUsage[];
  recent_activity: RecentActivity[];
};

export async function getDashboardStats(): Promise<DashboardStats> {
  return platformJson<DashboardStats>({
    path: "/stats/dashboard",
    method: "GET",
  });
}
