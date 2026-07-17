"use client";

import { platformJson } from "@/lib/auth-fetch";

export type ChannelDailyQuota = {
  profile_id: string;
  profile_name: string;
  daily_songs_used: number;
  daily_songs_limit: number;
  daily_songs_remaining: number;
  daily_images_used: number;
  daily_images_limit: number;
  daily_images_remaining: number;
};

export type QuotaStatus = {
  songs_remaining: number | null;
  songs_quota: number | null;
  images_remaining: number | null;
  images_quota: number | null;
  drafts_remaining?: number | null;
  drafts_quota?: number | null;
  videos_remaining?: number | null;
  videos_quota?: number | null;
  merges_remaining?: number | null;
  merges_quota?: number | null;
  daily_videos_remaining?: number | null;
  daily_videos_limit?: number | null;
  daily_merges_remaining?: number | null;
  daily_merges_limit?: number | null;
  wallet_balance: number;
  channels: ChannelDailyQuota[];
};

export async function getQuotaStatus(): Promise<QuotaStatus> {
  return platformJson<QuotaStatus>({
    path: "/credits/quota-status",
    method: "GET",
  });
}
